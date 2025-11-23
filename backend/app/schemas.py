
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field

from .models import Role, TaskEventType, TaskStatus


class ORMModel(BaseModel):
    class Config:
        from_attributes = True


# ---------------- Comments ----------------


class CommentCreate(BaseModel):
    text: str


class CommentOut(ORMModel):
    id: int
    task_id: int
    author: str
    text: str
    created_at: datetime


# ---------------- Users ----------------


class UserBase(ORMModel):
    id: int
    name: str
    email: EmailStr
    role: Role

class UserOut(UserBase):
    pass

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: Role = Role.USER
    password: str = Field(min_length=4)

# ---------------- Students & absences ----------------

class StudentIn(BaseModel):
    # Grunninfo
    name: str
    student_class: Optional[str] = None   # f.eks. "11"
    address: Optional[str] = None

    # Fra Excel / ekstern kilde
    gender: Optional[str] = None
    contact_name: Optional[str] = None
    contact_relationship: Optional[str] = None
    contact_phone: Optional[str] = None

    absent_today: Optional[bool] = None

    # Attendance-snapshots
    attendance_ytd: Optional[float] = None
    attendance_last_week: Optional[float] = None
    attendance_last_2_weeks: Optional[float] = None
    attendance_last_3_weeks: Optional[float] = None
    attendance_last_4_weeks: Optional[float] = None

    # Evt. gamle snapshot-felter (kan beholdes for kompatibilitet)
    attendance_pct: Optional[int] = None
    absence_pct: Optional[int] = None
    last_absence_date: Optional[date] = None
    last_absence_reason: Optional[str] = None


class StudentOut(ORMModel):
    id: int

    name: str
    student_class: Optional[str]
    address: Optional[str]

    gender: Optional[str] = None
    contact_name: Optional[str] = None
    contact_relationship: Optional[str] = None
    contact_phone: Optional[str] = None

    absent_today: Optional[bool] = None

    attendance_ytd: Optional[float] = None
    attendance_last_week: Optional[float] = None
    attendance_last_2_weeks: Optional[float] = None
    attendance_last_3_weeks: Optional[float] = None
    attendance_last_4_weeks: Optional[float] = None

    attendance_pct: Optional[int] = None
    absence_pct: Optional[int] = None
    last_absence_date: Optional[date] = None
    last_absence_reason: Optional[str] = None


class AbsenceIn(BaseModel):
    student_id: int
    date: date
    reason_code: Optional[str] = None
    note: Optional[str] = None
    reported_by: Optional[str] = None


class AbsenceOut(ORMModel):
    id: int
    student_id: int
    date: date
    reason_code: Optional[str]
    note: Optional[str]
    reported_by: Optional[str]
    created_at: datetime


# ---------------- Tasks ----------------


class ChecklistItem(BaseModel):
    text: str
    done: bool = False


class TaskIn(BaseModel):
    student_id: int
    title: str

    body: Optional[str] = None
    address: Optional[str] = None

    due_at: Optional[datetime] = None
    assignee_user_id: Optional[int] = None

    checklist: List[ChecklistItem] = []
    external_ref: Optional[str] = None

    # Snapshot fields for the Home Visit use case (optional)
    attendance_pct: Optional[int] = None
    last_absence_date: Optional[date] = None
    last_absence_reason: Optional[str] = None
    visit_notes: Optional[str] = None


class TaskOut(TaskIn, ORMModel):
    id: int
    status: TaskStatus
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class TaskEdit(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    address: Optional[str] = None
    due_at: Optional[datetime] = None
    assignee_user_id: Optional[int] = None
    checklist: Optional[List[ChecklistItem]] = None
    external_ref: Optional[str] = None

    # "reason" is unified into Task.body in the backend
    reason: Optional[str] = None


class AssignIn(BaseModel):
    assignee_user_id: int


class StatusIn(BaseModel):
    action: Literal["accept", "reject", "complete"]
    reason: Optional[str] = None


# ---------------- Events & history ----------------


class TaskEventOut(ORMModel):
    id: int
    task_id: int
    type: TaskEventType
    meta: Optional[Dict[str, Any]] = None
    actor_user_id: int
    created_at: datetime


class HistoryItem(BaseModel):
    kind: Literal["absence", "visit"]
    date: datetime
    title: Optional[str] = None
    reason_code: Optional[str] = None
    note: Optional[str] = None
    reported_by: Optional[str] = None

class BatchSettingsOut(BaseModel):
    rollover_hour: int

    class Config:
        from_attributes = True


class BatchSettingsUpdate(BaseModel):
    rollover_hour: int
