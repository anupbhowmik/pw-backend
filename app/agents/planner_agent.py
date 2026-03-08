"""Planner Agent — financial planning chat with transaction context."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Category, Transaction, User
from app.prompts.planner import PLANNER_SYSTEM, PLANNER_USER_TEMPLATE
from app.services.llm import call_text

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Handles financial planning chat. Fetches recent transactions as context
    and passes the full conversation history to the LLM."""

    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    async def _get_recent_transactions(self, limit: int = 30) -> list[Transaction]:
        """Fetch the most recent transactions with items and category."""
        stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.items),
            )
            .where(Transaction.user_id == self.user_id)
            .order_by(Transaction.purchase_date.desc(), Transaction.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_user_budget_info(self) -> dict:
        """Fetch user budget fields."""
        result = await self.db.execute(
            select(User).where(User.id == self.user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return {}
        return {
            "monthly_income": user.monthly_income,
            "monthly_rent": user.monthly_rent,
            "monthly_gym_subscription": user.monthly_gym_subscription,
            "monthly_insurance": user.monthly_insurance,
        }

    async def _get_category_name(self, category_id: int | None) -> str | None:
        """Look up category name by id."""
        if not category_id:
            return None
        result = await self.db.execute(
            select(Category.name).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()

    def _format_transactions(self, transactions: list[Transaction], category_map: dict[int, str]) -> str:
        """Format transactions into a readable text block for the LLM."""
        if not transactions:
            return "No transactions found."

        lines = []
        for txn in transactions:
            date_str = txn.purchase_date.strftime("%Y-%m-%d") if txn.purchase_date else "Unknown date"
            cat_name = category_map.get(txn.category_id, "Uncategorized") if txn.category_id else "Uncategorized"
            location = ""
            if txn.store_city and txn.store_state:
                location = f" ({txn.store_city}, {txn.store_state})"

            line = f"- {date_str} | {txn.merchant_name}{location} | ${txn.total:.2f} | {cat_name}"

            # Add top items
            if txn.items:
                item_strs = []
                for item in txn.items[:5]:
                    name = item.description_norm or item.description_raw
                    item_strs.append(f"{name} ${item.total_price:.2f}")
                line += f"\n  Items: {', '.join(item_strs)}"
                if len(txn.items) > 5:
                    line += f" (+{len(txn.items) - 5} more)"

            lines.append(line)

        return "\n".join(lines)

    def _format_budget_info(self, budget: dict) -> str:
        """Format user budget info for the LLM."""
        parts = []
        if budget.get("monthly_income"):
            parts.append(f"Monthly income: ${budget['monthly_income']:.2f}")
        if budget.get("monthly_rent"):
            parts.append(f"Monthly rent: ${budget['monthly_rent']:.2f}")
        if budget.get("monthly_gym_subscription"):
            parts.append(f"Monthly gym: ${budget['monthly_gym_subscription']:.2f}")
        if budget.get("monthly_insurance"):
            parts.append(f"Monthly insurance: ${budget['monthly_insurance']:.2f}")
        return "\n".join(parts) if parts else "No budget info provided."

    def _format_conversation(self, messages: list[dict]) -> str:
        """Format chat history into a conversation string."""
        lines = []
        for msg in messages:
            if msg.get("user"):
                lines.append(f"User: {msg['user']}")
            if msg.get("airesponse"):
                lines.append(f"Assistant: {msg['airesponse']}")
        return "\n".join(lines)

    async def chat(self, messages: list[dict]) -> str:
        """Generate a response to the user's financial planning chat.

        Args:
            messages: List of {"user": "...", "airesponse": "..."} dicts.

        Returns:
            The LLM's response string.
        """
        transactions = await self._get_recent_transactions()
        budget = await self._get_user_budget_info()

        # Build category map for formatting
        cat_ids = {txn.category_id for txn in transactions if txn.category_id}
        category_map: dict[int, str] = {}
        for cat_id in cat_ids:
            name = await self._get_category_name(cat_id)
            if name:
                category_map[cat_id] = name

        txn_text = self._format_transactions(transactions, category_map)
        budget_text = self._format_budget_info(budget)
        conv_text = self._format_conversation(messages)

        user_prompt = PLANNER_USER_TEMPLATE.format(
            transactions=txn_text,
            budget_info=budget_text,
            conversation=conv_text,
        )

        logger.info("Planner chat prompt length: %d chars", len(user_prompt))

        response = await call_text(PLANNER_SYSTEM, user_prompt)
        return response
