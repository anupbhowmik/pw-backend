"""Feed routes — personalized shopping suggestions and transaction summaries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.agents.feed_agent import FeedAgent
from app.models.models import User
from app.schemas.schemas import FeedItemResponse, FeedListResponse

router = APIRouter(prefix="/v1", tags=["feed"])


@router.get("/feed", response_model=FeedListResponse)
async def get_feed(
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = FeedAgent(db=db, user_id=user.id)
    feed_items = await agent.generate(days=days)

    return FeedListResponse(
        feeds=[FeedItemResponse(**item) for item in feed_items],
        count=len(feed_items),
    )
