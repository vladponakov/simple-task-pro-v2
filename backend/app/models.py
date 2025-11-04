# ================================================================
# BLOCK: MODELS
# Purpose: SQLAlchemy models and enums (align with frontend/seed)
# ================================================================
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON

Base = declarative_base()

# ---- Role enum expected by seed.py (DB still stores plain strings) ----
class Role(str, Enum):
    ADMIN = "Admin"
    USER = "User"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=True)
    name = Column(String(255))
    role = Column(String(50), default=Role.USER.value, nullable=False)  # "Admin" / "User"
    created_at = Column(DateTime, default=datetime.utcnow)

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    # Optional fields; seed.py sets these only if present on the model
    # Uncomment and run a migration (or use --reset) if you want them in DB:
    # student_class = Column(String(50), nullable=True)
    # address = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    title = Column(String(255), nullable=False)
    address = Column(String(255))  # kept to display a location/reason on tasks
    body = Column(Text)  # reason/details
    due_at = Column(DateTime, nullable=True)
    assignee_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Status values used in frontend: "New" | "Assigned" | "Rejected" | "Done"
    status = Column(String(20), default="New", nullable=False)
    checklist = Column(SQLITE_JSON, default=list)  # [{text, done}]
    external_ref = Column(String(255), nullable=True)  # e.g., Make.com row id
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    student = relationship("Student")
    assignee = relationship("User", foreign_keys=[assignee_user_id])

class TaskComment(Base):
    __tablename__ = "task_comments"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    author = Column(String(255))
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class StudentHistory(Base):
    __tablename__ = "student_history"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    type = Column(String(50))  # "absence" / "visit" / etc.
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
