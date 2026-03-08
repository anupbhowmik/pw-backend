"""Planner routes — financial planning chat."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User
from app.agents.planner_agent import PlannerAgent
from app.schemas.schemas import PlannerChatRequest, PlannerChatResponse

router = APIRouter(prefix="/v1", tags=["planner"])


@router.post("/planner/chat", response_model=PlannerChatResponse)
async def planner_chat(
    body: PlannerChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Chat with the financial planner. Accepts conversation history and
    returns an LLM response grounded in the user's recent transactions."""
    agent = PlannerAgent(db=db, user_id=user.id)
    messages = [m.model_dump() for m in body.messages]
    response = await agent.chat(messages)
    return PlannerChatResponse(response=response)
