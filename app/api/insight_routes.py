"""Insight, notification, and spending routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Insight, Notification, User
from app.agents.insight_agent import InsightAgent
from app.agents.planner_agent import PlannerAgent
from app.schemas.schemas import (
    InsightListResponse,
    InsightResponse,
    NotificationListResponse,
    NotificationResponse,
    ReminderRequest,
)

router = APIRouter(prefix="/v1", tags=["insights"])


# ------------------------------------------------------------------ #
# GET /v1/insights
# ------------------------------------------------------------------ #


@router.get("/insights", response_model=InsightListResponse)
async def get_insights(
    limit: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = InsightAgent(db=db, user_id=user.id)
    insights = await agent.generate(limit=limit)

    return InsightListResponse(
        insights=[_insight_to_response(i) for i in insights],
        count=len(insights),
    )


# ------------------------------------------------------------------ #
# GET /v1/notifications
# ------------------------------------------------------------------ #


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return NotificationListResponse(
        notifications=[_notif_to_response(n) for n in rows],
        count=len(rows),
    )


# ------------------------------------------------------------------ #
# POST /v1/notifications/reminder
# ------------------------------------------------------------------ #


@router.post("/notifications/reminder", response_model=NotificationResponse, status_code=201)
async def create_reminder(
    body: ReminderRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = PlannerAgent(db=db, user_id=user.id)
    notif = await agent.create_reminder(body.title, body.body, body.scheduled_at)
    return _notif_to_response(notif)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _insight_to_response(i: Insight) -> InsightResponse:
    return InsightResponse(
        id=i.id,
        type=i.type,
        title=i.title,
        desc=i.desc,
        severity=i.severity,
        details=i.details,
        is_read=i.is_read,
        created_at=i.created_at,
    )


def _notif_to_response(n: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=n.id,
        type=n.type,
        title=n.title,
        body=n.body,
        channel=n.channel,
        is_read=n.is_read,
        scheduled_at=n.scheduled_at,
        created_at=n.created_at,
    )
