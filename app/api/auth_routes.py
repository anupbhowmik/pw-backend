"""Auth routes — Google OAuth, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    verify_google_token,
)
from app.models.models import User
from app.schemas.schemas import (
    AuthContinueResponse,
    GoogleAuthRequest,
    UserResponse,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


# ------------------------------------------------------------------ #
# POST /v1/auth/google  — verify Google token, upsert user, return JWT
# ------------------------------------------------------------------ #


@router.post("/google", response_model=AuthContinueResponse)
async def auth_google(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """Verify Google OAuth token, create or update user, return Halkhata JWT."""
    # 1. Verify the Google token
    google_info = verify_google_token(body.token)

    google_id = google_info.get("sub")
    email = google_info.get("email")
    name = google_info.get("name")
    picture = google_info.get("picture")

    if not google_id or not email:
        raise HTTPException(status_code=401, detail="Invalid Google token: missing user info")

    # 2. Find or create user
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            google_id=google_id,
            email=email,
            display_name=name,
            picture=picture,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.email = email
        user.display_name = name or user.display_name
        user.picture = picture or user.picture
        await db.commit()
        await db.refresh(user)

    # 3. Issue our JWT
    token = create_access_token(user.id)

    return AuthContinueResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            picture=user.picture,
            currency=user.currency,
            timezone=user.timezone,
            created_at=user.created_at,
        ),
        access_token=token,
    )


# ------------------------------------------------------------------ #
# GET /v1/auth/user_profile  — current user profile
# ------------------------------------------------------------------ #


@router.get("/user/profile", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        picture=user.picture,
        currency=user.currency,
        timezone=user.timezone,
        created_at=user.created_at,
    )
