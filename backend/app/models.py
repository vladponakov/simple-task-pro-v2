from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum, JSON, Date, func
import enum
from .db import Base

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
    checklist = Column(JSON, nullable=True)
    due_at = Column(DateTime, nullable=True)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.NEW, nullable=False)
    assignee_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

class TaskEvent(Base):
    __tablename__ = "task_events"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    type = Column(SAEnum(TaskEventType), nullable=False)
    # was: metadata = Column(JSON, nullable=True)  <-- reserved!
    meta = Column("metadata", JSON, nullable=True)  # ORM attribute 'meta', DB column name 'metadata'
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
