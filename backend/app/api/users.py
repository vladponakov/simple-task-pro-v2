# ================================================================
# BLOCK: USERS_ROUTER
# Purpose: create/delete simple users
# ================================================================
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..db import SessionLocal
from ..models import User
from ..schemas import UserCreate, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.post("", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    u = User(email=payload.email, name=payload.name, role="User")
    db.add(u); db.commit(); db.refresh(u)
    return u

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    u = db.query(User).get(user_id)
    if not u:
        raise HTTPException(404, "User not found")
    db.delete(u); db.commit()
    return {"ok": True}
