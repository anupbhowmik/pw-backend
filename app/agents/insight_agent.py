"""Insight Agent — spending aggregation, spike detection, and insight generation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Insight, Notification
from app.tools.tools import db_compute_spending

logger = logging.getLogger(__name__)


class InsightAgent:
    """Generates spending insights and detects anomalies."""

    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    async def generate(self, limit: int = 5) -> list[Insight]:
        """Run all insight generators and return new insights."""
        insights: list[Insight] = []
        insights.extend(await self._detect_spending_spikes())
        insights.extend(await self._generate_category_summaries())
        return insights[:limit]

    async def _detect_spending_spikes(self) -> list[Insight]:
        """Detect categories where current month spending > 1.5x previous month avg."""
        now = datetime.now(timezone.utc)
        current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_start = (current_start - timedelta(days=1)).replace(day=1)

        current = await db_compute_spending(self.db, self.user_id, current_start, now)
        previous = await db_compute_spending(self.db, self.user_id, prev_start, current_start)

        prev_map = {s["category"]: s["total_spent"] for s in previous}
        insights: list[Insight] = []

        for s in current:
            prev_amt = prev_map.get(s["category"], 0)
            if prev_amt > 0 and s["total_spent"] > prev_amt * 1.5:
                insight = Insight(
                    user_id=self.user_id,
                    type="spending_spike",
                    title=f"Spending spike: {s['category']}",
                    desc=f"You've spent ${s['total_spent']:.2f} on {s['category']} this month, "
                         f"up from ${prev_amt:.2f} last month ({s['total_spent']/prev_amt:.1f}x).",
                    severity="warning",
                    details=f"Your {s['category']} spending of ${s['total_spent']:.2f} this month is {s['total_spent']/prev_amt:.1f}x higher than last month's ${prev_amt:.2f}. Consider reviewing recent purchases in this category.",
                )
                self.db.add(insight)
                insights.append(insight)

                # Create notification for spike
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

    async def _generate_category_summaries(self) -> list[Insight]:
        """Generate a summary insight of top spending categories this month."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        spending = await db_compute_spending(self.db, self.user_id, month_start, now)

        if not spending:
            return []

        total = sum(s["total_spent"] for s in spending)
        top3 = spending[:3]
        summary_lines = [f"  {s['category']}: ${s['total_spent']:.2f} ({s['percentage']}%)" for s in top3]

        insight = Insight(
            user_id=self.user_id,
            type="category_summary",
            title=f"Monthly spending: ${total:.2f}",
            desc=f"Top categories this month:\n" + "\n".join(summary_lines),
            severity="info",
            details=f"Your total spending this month is ${total:.2f}. Top categories: " + "; ".join(f"{s['category']} at ${s['total_spent']:.2f} ({s['percentage']}%)" for s in top3) + ".",
        )
        self.db.add(insight)
        await self.db.commit()
        return [insight]
