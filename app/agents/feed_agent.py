"""Feed Agent — product price comparisons via web search + recent transaction summaries."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Category, Transaction, TransactionItem
from app.prompts.feed import FEED_SYSTEM, FEED_USER_TEMPLATE
from app.services.llm import call_text_with_search

logger = logging.getLogger(__name__)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


class FeedAgent:
    """Generates a feed of price comparisons and transaction summaries."""

    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    # Data gathering from DB
    async def _get_date_range(self, days: int) -> tuple[datetime, datetime]:
        """Return (start, end) for the query window.

        Uses now() if recent transactions exist, otherwise falls back
        to the user's latest transaction date.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        result = await self.db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.user_id == self.user_id,
                Transaction.purchase_date >= cutoff,
            )
        )
        if result.scalar() > 0:
            return cutoff, now

        # Fall back to latest transaction date
        result = await self.db.execute(
            select(func.max(Transaction.purchase_date)).where(
                Transaction.user_id == self.user_id,
            )
        )
        latest = result.scalar()
        if latest is None:
            return cutoff, now
        return latest - timedelta(days=days), latest

    async def _get_transactions_with_items(
        self, start: datetime, end: datetime
    ) -> list[Transaction]:
        """Fetch transactions with their line items in the date range."""
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.items))
            .where(
                Transaction.user_id == self.user_id,
                Transaction.purchase_date >= start,
                Transaction.purchase_date < end,
            )
            .order_by(Transaction.purchase_date.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # Product extraction
    def _extract_products(self, transactions: list[Transaction]) -> list[dict]:
        """Pull notable products from transaction line items for comparison."""
        products = []
        for txn in transactions:
            for item in txn.items:
                if item.total_price and item.total_price >= 1.0:
                    products.append({
                        "name": item.description_norm or item.description_raw,
                        "price": round(float(item.total_price), 2),
                        "unit_price": round(float(item.unit_price), 2) if item.unit_price else None,
                        "quantity": item.quantity,
                        "store": txn.merchant_name,
                        "date": txn.purchase_date.strftime("%Y-%m-%d") if txn.purchase_date else None,
                        "city": txn.store_city,
                        "state": txn.store_state,
                    })

        # Sort by price descending, take top 20 for LLM consideration
        products.sort(key=lambda p: p["price"], reverse=True)
        return products[:20]

    def _format_product_list(self, products: list[dict]) -> str:
        lines = []
        for p in products:
            qty_str = f" (qty: {p['quantity']})" if p['quantity'] and p['quantity'] != 1 else ""
            unit_str = f" @ ${p['unit_price']}/ea" if p['unit_price'] else ""
            lines.append(
                f"- {p['name']}: ${p['price']}{unit_str}{qty_str} at {p['store']} on {p['date']}"
            )
        return "\n".join(lines) if lines else "No products found."

    def _get_location_context(self, transactions: list[Transaction]) -> str:
        """Build a location string from recent transactions."""
        locations = set()
        for txn in transactions:
            if txn.store_city and txn.store_state:
                locations.add(f"{txn.store_city}, {txn.store_state}")
            elif txn.store_state:
                locations.add(txn.store_state)
        return "; ".join(locations) if locations else "US"

    # Transaction summaries
    def _build_transaction_summaries(self, transactions: list[Transaction], count: int = 3) -> list[dict]:
        """Build summary feed items for the most recent transactions."""
        summaries = []
        for txn in transactions[:count]:
            item_names = [
                item.description_norm or item.description_raw
                for item in txn.items
            ]
            top_items = item_names[:5]

            date_str = txn.purchase_date.strftime("%b %d") if txn.purchase_date else "Unknown date"
            location = ""
            if txn.store_city and txn.store_state:
                location = f" in {txn.store_city}, {txn.store_state}"

            summaries.append({
                "type": "transaction_summary",
                "title": f"{txn.merchant_name} — {date_str}",
                "desc": (
                    f"You spent ${txn.total:.2f} on {len(txn.items)} item(s) "
                    f"at {txn.merchant_name}{location}."
                ),
                "merchant": txn.merchant_name,
                "total": round(float(txn.total), 2) if txn.total else 0,
                "item_count": len(txn.items),
                "top_items": top_items,
                "purchase_date": txn.purchase_date.isoformat() if txn.purchase_date else None,
            })
        return summaries

    # Price comparison via LLM + web search
    async def _generate_price_comparisons(self, products: list[dict], location: str) -> list[dict]:
        """Call LLM with search grounding to find better prices."""
        if not products:
            return []

        product_list = self._format_product_list(products)
        user_prompt = FEED_USER_TEMPLATE.format(
            days=30,
            product_list=product_list,
            location=location,
        )

        logger.info("Feed LLM prompt:\n%s", user_prompt)

        try:
            raw = await call_text_with_search(FEED_SYSTEM, user_prompt)
        except Exception:
            logger.exception("Feed LLM call failed")
            return []

        raw = _strip_fences(raw)

        try:
            comparisons = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse feed LLM response: %s", raw)
            return []

        if not isinstance(comparisons, list):
            comparisons = [comparisons]

        return comparisons[:4]

    # Public API
    async def generate(self, days: int = 30) -> list[dict]:
        """Generate the full feed: price comparisons + transaction summaries."""
        start, end = await self._get_date_range(days)
        transactions = await self._get_transactions_with_items(start, end)

        if not transactions:
            return [{
                "type": "empty",
                "title": "No Recent Activity",
                "desc": "Upload receipts to start getting personalized shopping suggestions.",
                "merchant": None,
                "total": None,
                "item_count": None,
                "top_items": [],
                "purchase_date": None,
            }]

        feed: list[dict] = []

        # 1. Transaction summaries (most recent 2-3)
        summaries = self._build_transaction_summaries(transactions, count=3)
        feed.extend(summaries)

        # 2. Price comparisons via LLM + web search
        products = self._extract_products(transactions)
        if products:
            location = self._get_location_context(transactions)
            comparisons = await self._generate_price_comparisons(products, location)
            feed.extend(comparisons)

        return feed
