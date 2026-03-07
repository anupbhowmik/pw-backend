"""Planner Agent — Phase 2 stub. Only reminders work in Phase 1."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Notification

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Handles planning features. Phase 1: simple reminders only."""

    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    async def create_reminder(
        self, title: str, body: str, scheduled_at: datetime
    ) -> Notification:
        """Create a scheduled reminder notification."""
        notif = Notification(
            user_id=self.user_id,
            type="reminder",
            title=title,
            body=body,
            scheduled_at=scheduled_at,
        )
        self.db.add(notif)
        await self.db.commit()
        await self.db.refresh(notif)
        logger.info("Created reminder %s for user %s at %s", notif.id, self.user_id, scheduled_at)
        return notif
