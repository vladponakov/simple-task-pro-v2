# deps.py
from __future__ import annotations

from fastapi import Depends, HTTPException, Security        # <-- add Security
from fastapi.security import APIKeyHeader                    # <-- add this
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Role
from app.config import settings

USER_FIXTURES = {
    "paddy": 1,   # Admin
    "ulf": 2,     # User 1
    "una": 3,     # User 2
}

# Expose X-User as an API key header in Swagger ("Authorize" button)
x_user_scheme = APIKeyHeader(name="X-User", auto_error=False)

def get_current_user(
    x_user: str | None = Security(x_user_scheme),           # <-- use Security(...) instead of Header(...)
    db: Session = Depends(get_db),
) -> User:
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

# --- API token helpers unchanged ---
def _bearer(authorization: str | None = None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()

def require_api_token(token: str | None = Depends(_bearer)) -> str:
    if not settings.REQUIRE_API_TOKEN:
        return "DEV_BYPASS"
    if token and token in (settings.API_TOKENS or []):
        return token
    raise HTTPException(status_code=401, detail="Invalid or missing API token")

def get_admin_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        raise HTTPException(status_code=500, detail="Admin user id=1 not found")
    return user
