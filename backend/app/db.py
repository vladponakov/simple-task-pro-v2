# backend/app/db.py
# ================================================================
# BLOCK: DB
# Purpose: use ONE shared Base (from models) so create_all sees all tables
# ================================================================
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base  # <- IMPORTANT: import Base from models.py

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
