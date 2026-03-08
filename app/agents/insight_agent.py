"""Insight Agent — spending aggregation, spike detection, and LLM insight generation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Insight, Notification, Transaction
from app.prompts.insight import INSIGHT_SYSTEM, INSIGHT_USER_TEMPLATE
from app.services.llm import call_text
from app.tools.tools import db_compute_spending

logger = logging.getLogger(__name__)


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

    async def _gather_spending_context(self) -> tuple[str, str, str]:
        """Build monthly and biweekly spending summaries for the LLM.

        Returns (monthly_data, biweekly_data, spike_section).
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

        # --- Spending spikes (current vs previous month) ---
        current_spending = await db_compute_spending(self.db, self.user_id, current_start, current_end)
        prev_spending = await db_compute_spending(self.db, self.user_id, prev_start, prev_end)
        prev_map = {s["category"]: s["total_spent"] for s in prev_spending}

        spikes = []
        for s in current_spending:
            prev_amt = prev_map.get(s["category"], 0)
            if prev_amt > 0 and s["total_spent"] > prev_amt * 1.3:
                ratio = s["total_spent"] / prev_amt
                spikes.append(f"  - {s['category']}: ${s['total_spent']:.2f} vs ${prev_amt:.2f} last month ({ratio:.1f}x increase)")

        spike_section = ""
        if spikes:
            spike_section = "## Spending Spikes Detected\n" + "\n".join(spikes)

        return "\n\n".join(months_data), "\n\n".join(biweekly_data), spike_section

    async def generate(self, limit: int = 5) -> list[Insight]:
        """Gather spending data, send to LLM, parse response into Insights."""
        monthly_data, biweekly_data, spike_section = await self._gather_spending_context()

        # If all 3 months are empty, let the LLM return the insufficient-data warning
        all_empty = monthly_data.count("No transactions.") == 3

        user_prompt = INSIGHT_USER_TEMPLATE.format(
            months=3,
            monthly_data=monthly_data,
            biweekly_data=biweekly_data,
            spike_section=spike_section,
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

            notif = Notification(
                user_id=self.user_id,
                type="insight",
                title=insight.title,
                body=insight.desc,
                related_id=insight.id,
                related_type="insight",
            )
            self.db.add(notif)

        if insights:
            await self.db.commit()
        return insights
