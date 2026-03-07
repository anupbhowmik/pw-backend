"""JWT authentication and Google OAuth token verification."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.database import get_db
from app.models.models import User

bearer_scheme = HTTPBearer()


# ------------------------------------------------------------------ #
# Google OAuth
# ------------------------------------------------------------------ #


def verify_google_token(token: str) -> dict:
    """Verify Google OAuth token and return user info.

    Args:
        token: Google OAuth token from the frontend

    Returns:
        dict with user info (sub, email, name, picture)

    Raises:
        HTTPException: If token is invalid or verification fails
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google Client ID not configured",
        )

    try:
        idinfo = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )

        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer",
            )

        logger.info("Google OAuth verified for email=%s", idinfo.get("email"))
        return idinfo
    except ValueError as e:
        logger.error("Google token ValueError: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {e}",
        )
    except google_exceptions.GoogleAuthError as e:
        logger.error("Google auth error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google authentication failed: {e}",
        )
    except Exception as e:
        logger.error("Unexpected Google token error: %s: %s", type(e).__name__, e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {e}",
        )


# ------------------------------------------------------------------ #
# JWT
# ------------------------------------------------------------------ #


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def validate_token(token: str) -> tuple[bool, str]:
    """Validate a JWT bearer token without raising exceptions.

    Returns (True, token) if valid, (False, "") if invalid/expired.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("sub") is None:
            return False, ""
        return True, token
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return False, ""


def decode_token(token: str) -> str:
    """Return user_id from token or raise HTTPException."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ------------------------------------------------------------------ #
# FastAPI dependency
# ------------------------------------------------------------------ #


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate our JWT and return the User. Used on all protected endpoints."""
    is_valid, _ = validate_token(credentials.credentials)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user_id = decode_token(credentials.credentials)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
