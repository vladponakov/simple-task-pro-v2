from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Role

HEADER_TO_USER = {
    "anna": {"name": "Anna Admin", "role": Role.ADMIN},
    "ulf": {"name": "Ulf", "role": Role.USER},
    "una": {"name": "Una", "role": Role.USER},
}

def get_current_user(x_user: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not x_user or x_user not in HEADER_TO_USER:
        raise HTTPException(status_code=401, detail="Missing or invalid X-User header")
    u = db.query(User).filter(User.name == HEADER_TO_USER[x_user]["name"]).first()
    if not u:
        u = User(name=HEADER_TO_USER[x_user]["name"], role=HEADER_TO_USER[x_user]["role"])
        db.add(u); db.commit(); db.refresh(u)
    return u

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")
    return user
