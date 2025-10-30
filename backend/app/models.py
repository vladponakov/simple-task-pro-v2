import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, JSON, Date, func
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableList

from .db import Base


# ---------------- Enums ----------------
class Role(str, enum.Enum):
    ADMIN = "Admin"
    USER = "User"


class TaskStatus(str, enum.Enum):
    NEW = "New"
    ASSIGNED = "Assigned"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    DONE = "Done"


class TaskEventType(str, enum.Enum):
    EDIT = "Edit"
    ASSIGN = "Assign"
    REASSIGN = "Reassign"
    DELETE = "Delete"
    RESTORE = "Restore"
    ACCEPT = "Accept"
    REJECT = "Reject"
    COMPLETE = "Complete"


# ---------------- Core tables ----------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(SAEnum(Role), nullable=False)


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    student_class = Column(String, nullable=True)
    address = Column(String, nullable=True)


class Absence(Base):
    __tablename__ = "absences"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    reason_code = Column(String, nullable=False)
    note = Column(Text, nullable=True)
    reported_by = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)

    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    address = Column(String, nullable=True)

    # Nytt felt: årsak/beskrivelse
    reason = Column(String, nullable=True)

    # Sjekkliste lagres som JSON-liste [{text, done}], MutableList gjør at endringer fanges opp
    checklist = Column(MutableList.as_mutable(JSON), nullable=True, default=list)

    due_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.NEW, nullable=False)

    assignee_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    author = Column(String, nullable=True)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("Task", backref="comments", passive_deletes=True)


class TaskEvent(Base):
    __tablename__ = "task_events"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    type = Column(SAEnum(TaskEventType), nullable=False)

    # 'metadata' er reservert i SQLAlchemy → bruk DB-kolonnen "metadata", ORM-felt 'meta'
    meta = Column("metadata", JSON, nullable=True)

    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
