# backend/app/deps.py
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Role
from app.config import settings

# ---- Demo users mapping (header "X-User") -----------------------------------
# Keep only the users you actually have in your DB.
USER_FIXTURES = {
    "paddy": 1,  # Admin (Paddy MacGrath)
    "ulf":   2,  # User 1
    "una":   3,  # User 2
    # "liam":  4,  # User 3 (remove if you dropped him)
}

def get_current_user(
    x_user: str | None = Header(None, convert_underscores=True),
    db: Session = Depends(get_db),
) -> User:
    """
    Auth via custom header 'X-User' sent by the frontend.
    Maps short id -> fixed user ID (USER_FIXTURES), then loads from DB.
    """
    key = (x_user or "").strip().lower()
    uid = USER_FIXTURES.get(key)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

# ---- API token helpers (for server-to-server ingest) ------------------------

def _bearer(authorization: str | None = Header(None)) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()

def require_api_token(token: str | None = Depends(_bearer)) -> str:
    """
    When settings.REQUIRE_API_TOKEN is False (dev), bypass the token.
    Otherwise the Bearer token must be one of settings.API_TOKENS.
    """
    if not settings.REQUIRE_API_TOKEN:
        return "DEV_BYPASS"
    if token and token in (settings.API_TOKENS or []):
        return token
    raise HTTPException(status_code=401, detail="Invalid or missing API token")

def get_admin_user(db: Session = Depends(get_db)) -> User:
    """
    Use the Admin (id=1) as the 'actor' for ingest endpoints.
    """
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        raise HTTPException(status_code=500, detail="Admin user id=1 not found")
    return user
