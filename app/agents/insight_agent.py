"""Insight Agent — spending aggregation, spike detection, and LLM insight generation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Category, Insight, Transaction
from app.prompts.insight import INSIGHT_SYSTEM, INSIGHT_USER_TEMPLATE
from app.services.llm import call_text
from app.tools.tools import db_compute_spending

logger = logging.getLogger(__name__)

MIN_TRANSACTIONS_FOR_LLM = 3


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


class InsightAgent:
    """Generates spending insights via LLM from aggregated spending data."""

    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    async def _get_reference_date(self) -> datetime:
        """Return now() if there are transactions this month,
        otherwise the user's latest transaction date."""
        now = datetime.now(timezone.utc)
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.user_id == self.user_id,
                Transaction.purchase_date >= current_month_start,
            )
        )
        if result.scalar() > 0:
            return now

        result = await self.db.execute(
            select(func.max(Transaction.purchase_date)).where(
                Transaction.user_id == self.user_id,
            )
        )
        latest = result.scalar()
        return latest if latest is not None else now

    def _month_bounds(self, ref: datetime) -> tuple[datetime, datetime]:
        start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end

    def _biweekly_bounds(self, month_start: datetime, month_end: datetime) -> list[tuple[str, datetime, datetime]]:
        """Split a month into two biweekly periods: 1st-15th and 16th-end."""
        mid = month_start.replace(day=16)
        month_label = month_start.strftime("%B %Y")
        return [
            (f"{month_label} (1st–15th)", month_start, mid),
            (f"{month_label} (16th–end)", mid, month_end),
        ]

    async def _count_transactions_in_month(self, start: datetime, end: datetime) -> int:
        """Count transactions for the user in a given date range."""
        result = await self.db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.user_id == self.user_id,
                Transaction.purchase_date >= start,
                Transaction.purchase_date < end,
            )
        )
        return result.scalar() or 0

    async def _get_transaction_details(self, start: datetime, end: datetime) -> list[dict]:
        """Fetch individual transaction details for a date range."""
        stmt = (
            select(
                Transaction.merchant_name,
                Transaction.store_city,
                Transaction.store_state,
                Transaction.purchase_date,
                Transaction.subtotal,
                Transaction.tax,
                Transaction.total,
                Transaction.payment_method,
                Category.name.label("category"),
            )
            .outerjoin(Category, Transaction.category_id == Category.id)
            .where(
                Transaction.user_id == self.user_id,
                Transaction.purchase_date >= start,
                Transaction.purchase_date < end,
            )
            .order_by(Transaction.purchase_date.desc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        return [
            {
                "merchant": r.merchant_name,
                "city": r.store_city,
                "state": r.store_state,
                "date": r.purchase_date.strftime("%Y-%m-%d") if r.purchase_date else None,
                "subtotal": round(float(r.subtotal), 2) if r.subtotal else None,
                "tax": round(float(r.tax), 2) if r.tax else None,
                "total": round(float(r.total), 2) if r.total else None,
                "payment_method": r.payment_method,
                "category": r.category or "Uncategorized",
            }
            for r in rows
        ]

    def _format_transaction_details(self, transactions: list[dict], label: str) -> str:
        """Format individual transaction details into a readable string."""
        if not transactions:
            return f"### {label}\nNo transactions."
        lines = []
        for t in transactions:
            location = ""
            if t["city"] and t["state"]:
                location = f" ({t['city']}, {t['state']})"
            elif t["city"]:
                location = f" ({t['city']})"

            tax_str = f", tax: ${t['tax']}" if t['tax'] else ""
            payment_str = f", paid via {t['payment_method']}" if t['payment_method'] else ""

            lines.append(
                f"  - {t['date']} | {t['merchant']}{location} | "
                f"${t['total']}{tax_str}{payment_str} | {t['category']}"
            )
        return f"### {label}\n" + "\n".join(lines)

    async def _gather_spending_context(self) -> tuple[str, str, str, int]:
        """Build monthly and biweekly spending summaries plus transaction details.

        Returns (monthly_data, biweekly_data, transaction_details, latest_month_txn_count).
        """
        ref = await self._get_reference_date()
        current_start, current_end = self._month_bounds(ref)
        prev_start, prev_end = self._month_bounds(current_start - timedelta(days=1))
        two_ago_start, two_ago_end = self._month_bounds(prev_start - timedelta(days=1))

        month_windows = [
            (two_ago_start, two_ago_end),
            (prev_start, prev_end),
            (current_start, current_end),
        ]

        # Count transactions in the latest month
        latest_month_count = await self._count_transactions_in_month(current_start, current_end)

        # --- Monthly summary ---
        months_data = []
        for start, end in month_windows:
            label = start.strftime("%B %Y")
            spending = await db_compute_spending(self.db, self.user_id, start, end)
            if not spending:
                months_data.append(f"### {label}\nNo transactions.")
                continue
            total = sum(s["total_spent"] for s in spending)
            lines = [f"  - {s['category']}: ${s['total_spent']:.2f} ({s['percentage']}%) — {s['transaction_count']} transactions" for s in spending]
            months_data.append(f"### {label} (Total: ${total:.2f})\n" + "\n".join(lines))

        # --- Biweekly breakdown ---
        biweekly_data = []
        for start, end in month_windows:
            for bw_label, bw_start, bw_end in self._biweekly_bounds(start, end):
                spending = await db_compute_spending(self.db, self.user_id, bw_start, bw_end)
                if not spending:
                    biweekly_data.append(f"### {bw_label}\nNo transactions.")
                    continue
                total = sum(s["total_spent"] for s in spending)
                lines = [f"  - {s['category']}: ${s['total_spent']:.2f} ({s['percentage']}%) — {s['transaction_count']} transactions" for s in spending]
                biweekly_data.append(f"### {bw_label} (Total: ${total:.2f})\n" + "\n".join(lines))

        # --- Individual transaction details ---
        txn_details_parts = []
        for start, end in month_windows:
            label = start.strftime("%B %Y")
            txns = await self._get_transaction_details(start, end)
            txn_details_parts.append(self._format_transaction_details(txns, label))

        return (
            "\n\n".join(months_data),
            "\n\n".join(biweekly_data),
            "\n\n".join(txn_details_parts),
            latest_month_count,
        )

    def _build_no_data_insight(self) -> list[dict]:
        """Return a hardcoded warning when there are zero transactions."""
        return [{
            "type": "warning",
            "title": "No Receipts Yet",
            "desc": "Upload your first receipts to start getting spending insights.",
            "severity": "info",
            "details": (
                "We don't have any transaction data to work with yet. "
                "Once you start uploading receipts, we'll track your spending "
                "across categories and provide actionable tips to help you save. "
                "The more receipts you upload, the better your insights will be."
            ),
        }]

    def _build_summary_insight(self, transactions: list[dict]) -> list[dict]:
        """Build a single summary insight from a small number of transactions."""
        total_spent = sum(t["total"] for t in transactions if t["total"])
        merchants = [t["merchant"] for t in transactions if t["merchant"]]
        categories = list({t["category"] for t in transactions if t["category"]})
        dates = [t["date"] for t in transactions if t["date"]]

        merchant_list = ", ".join(merchants)
        category_list = ", ".join(categories)
        date_range = f"from {min(dates)} to {max(dates)}" if len(dates) > 1 else f"on {dates[0]}" if dates else ""

        return [{
            "type": "tip",
            "title": "Your Spending So Far",
            "desc": (
                f"You have {len(transactions)} receipt(s) totalling ${total_spent:.2f} "
                f"across {category_list}. Upload more receipts to unlock deeper insights!"
            ),
            "severity": "info",
            "details": (
                f"Your receipts {date_range} include purchases at {merchant_list}, "
                f"adding up to ${total_spent:.2f} in the {category_list} "
                f"{'category' if len(categories) == 1 else 'categories'}. "
                f"With just a few more receipts we can start identifying spending patterns, "
                f"detect trends across biweekly periods, and offer personalized savings tips."
            ),
        }]

    async def generate(self, limit: int = 5) -> list[Insight]:
        """Gather spending data, send to LLM, parse response into Insights."""
        monthly_data, biweekly_data, txn_details, latest_month_count = (
            await self._gather_spending_context()
        )

        if latest_month_count == 0:
            # Zero transactions — generic no-data warning
            insight_dicts = self._build_no_data_insight()
        elif latest_month_count < MIN_TRANSACTIONS_FOR_LLM:
            # 1-2 transactions — summarise the actual receipts
            ref = await self._get_reference_date()
            current_start, current_end = self._month_bounds(ref)
            transactions = await self._get_transaction_details(current_start, current_end)
            insight_dicts = self._build_summary_insight(transactions)
        else:
            user_prompt = INSIGHT_USER_TEMPLATE.format(
                months=3,
                monthly_data=monthly_data,
                biweekly_data=biweekly_data,
                transaction_details=txn_details,
            )
            logger.info("Insight LLM prompt:\n%s", user_prompt)

            raw = await call_text(INSIGHT_SYSTEM, user_prompt)
            raw = _strip_fences(raw)

            try:
                insight_dicts = json.loads(raw)
            except json.JSONDecodeError:
                logger.error("Failed to parse LLM insight response: %s", raw)
                return []

            if not isinstance(insight_dicts, list):
                insight_dicts = [insight_dicts]

        insights: list[Insight] = []
        for d in insight_dicts[:limit]:
            insight = Insight(
                user_id=self.user_id,
                type=d.get("type", "trend"),
                title=d.get("title", "Insight"),
                desc=d.get("desc", ""),
                severity=d.get("severity", "info"),
                details=d.get("details", ""),
            )
            self.db.add(insight)
            insights.append(insight)

        if insights:
            await self.db.commit()
        return insights
