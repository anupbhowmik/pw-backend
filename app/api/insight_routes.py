"""Insight routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Insight, User
from app.agents.insight_agent import InsightAgent
from app.schemas.schemas import (
    InsightListResponse,
    InsightResponse,
)

router = APIRouter(prefix="/v1", tags=["insights"])


# GET /v1/insights
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


# Helpers
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


