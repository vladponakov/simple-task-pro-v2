from __future__ import annotations

import enum
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Date,
    Enum as SAEnum,
    func,
    Boolean,
    Float,
)
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
    EDIT = "EDIT"
    ASSIGN = "ASSIGN"
    REASSIGN = "REASSIGN"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    COMPLETE = "COMPLETE"
    DELETE = "DELETE"
    RESTORE = "RESTORE"


# ---------------- Core models ----------------


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    role = Column(SAEnum(Role), nullable=False, default=Role.USER)
    password_hash = Column(String, nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    created_tasks = relationship(
        "Task",
        back_populates="creator",
        foreign_keys="Task.created_by",
    )
    assigned_tasks = relationship(
        "Task",
        back_populates="assignee",
        foreign_keys="Task.assignee_user_id",
    )

class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, default=1)
    rollover_hour = Column(Integer, nullable=False, default=18)
    rollover_timezone = Column(String, nullable=True)
    # senere kan du også legge til:
    # student_sync_hour = Column(Integer, nullable=False, default=7)
    # import_daily_hour = Column(Integer, nullable=False, default=8)
    # export_done_hour = Column(Integer, nullable=False, default=20)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)

    admission_number = Column(String, nullable=False, unique=True, index=True)

    # Navn / klasse / adresse (brukes i UI)
    name = Column(String, nullable=False)
    student_class = Column(String, nullable=True)
    address = Column(String, nullable=True)

    # Nytt: kobling mot master-Excel
    admission_number = Column(String, nullable=True, index=True)

    # Navnedeling (valgfritt, men fint å ha)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    gender = Column(String, nullable=True)

    # Kontaktinfo
    contact_name = Column(String, nullable=True)
    contact_relationship = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)

    # Om eleven er fraværende i dag
    absent_today = Column(Boolean, nullable=False, server_default="0")

    # Attendance fra Excel (% YtD og siste uker)
    attendance_ytd = Column(Float, nullable=True)
    attendance_last_week = Column(Float, nullable=True)
    attendance_last_2_weeks = Column(Float, nullable=True)
    attendance_last_3_weeks = Column(Float, nullable=True)
    attendance_last_4_weeks = Column(Float, nullable=True)

    # Gamle snapshot-felter – beholder for kompatibilitet
    attendance_pct = Column(Integer, nullable=True)
    absence_pct = Column(Integer, nullable=True)
    last_absence_date = Column(Date, nullable=True)
    last_absence_reason = Column(String, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    absences = relationship("Absence", back_populates="student", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="student")

class Absence(Base):
    __tablename__ = "absences"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False)
    reason_code = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    reported_by = Column(String, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    student = relationship("Student", back_populates="absences")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    title = Column(String, nullable=False)

    status = Column(
        SAEnum(TaskStatus),
        nullable=False,
        default=TaskStatus.NEW,
    )

    body = Column(Text, nullable=True)
    address = Column(String, nullable=True)

    checklist = Column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )

    # For external systems (Make.com etc.)
    external_ref = Column(String, nullable=True)

    assignee_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    due_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    student = relationship("Student", back_populates="tasks")
    assignee = relationship(
        "User",
        foreign_keys=[assignee_user_id],
        back_populates="assigned_tasks",
    )
    creator = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_tasks",
    )


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(
        Integer,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    task = relationship("Task", backref="comments", passive_deletes=True)


class TaskEvent(Base):
    __tablename__ = "task_events"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
    )
    type = Column(SAEnum(TaskEventType), nullable=False)

    # DB column is called "metadata" (reserved name), attribute is "meta"
    meta = Column("metadata", JSON, nullable=True)

    actor_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
