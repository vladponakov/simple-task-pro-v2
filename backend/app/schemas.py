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
    start_address: Optional[str] = None


class UserOut(UserBase):
    pass


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: Role = Role.USER
    password: str = Field(min_length=4)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[Role] = None
    password: Optional[str] = Field(default=None, min_length=4)
    start_address: Optional[str] = None


class MeUpdate(BaseModel):
    start_address: Optional[str] = None


# ---------------- Students & absences ----------------


class StudentIn(BaseModel):
    """
    Input fra Make.com for /api/batch/import_students.
    Dette matcher kolonnene i Excel.
    """

    admission_number: Optional[str] = None  # "Admission Number"

    year: Optional[str] = None  # "Year"
    first_name: str  # "First name"
    last_name: str  # "Last name"
    gender: Optional[str] = None  # "Gender"
    address: Optional[str] = None  # "Student address"

    contact_name: Optional[str] = None  # "Contact 1 Name"
    contact_relationship: Optional[str] = None  # "Contact 1 Relationship"
    contact_phone: Optional[str] = None  # "Contact 1 Telephone"

    # Absent Today → YES/NO i Excel, men Make.com konverterer til bool
    absent_today: bool = False

    # Attendance-prosent
    attendance_ytd: Optional[float] = None  # "% YtD"
    attendance_last_week: Optional[float] = None  # "Last week"
    attendance_last_2_weeks: Optional[float] = None
    attendance_last_3_weeks: Optional[float] = None
    attendance_last_4_weeks: Optional[float] = None

class StudentCreate(BaseModel):
    name: str
    student_class: Optional[str] = None
    address: Optional[str] = None

class StudentOut(ORMModel):
    id: int
    name: str
    student_class: Optional[str] = None
    address: Optional[str] = None

    admission_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None

    contact_name: Optional[str] = None
    contact_relationship: Optional[str] = None
    contact_phone: Optional[str] = None

    absent_today: bool = False

    attendance_ytd: Optional[float] = None
    attendance_last_week: Optional[float] = None
    attendance_last_2_weeks: Optional[float] = None
    attendance_last_3_weeks: Optional[float] = None
    attendance_last_4_weeks: Optional[float] = None

    attendance_pct: Optional[int] = None
    absence_pct: Optional[int] = None
    last_absence_date: Optional[date] = None
    last_absence_reason: Optional[str] = None

    created_at: datetime
    updated_at: datetime


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
    """
    Input når man oppretter en Task.

    NB:
    - title blir ignorert i backend ved opprettelse; vi setter alltid tittel fra Student
      (f.eks. "FirstName LastName").
    - body brukes som "reason" hvis satt, ellers blir det "Home Visite" i utils.create_home_visit_task_for_student.
    """

    student_id: int
    title: Optional[str] = None  # gjøres valgfri, backend setter tittel selv

    body: Optional[str] = None
    address: Optional[str] = None

    due_at: Optional[datetime] = None
    assignee_user_id: Optional[int] = None

    checklist: List[ChecklistItem] = Field(default_factory=list)
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
    student_admission_number: Optional[str] = None


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


class DoneExportItem(BaseModel):
    """
    Brukes av /api/batch/export_done.
    Dette er payload-en Make.com får tilbake.
    """

    admission_number: str
    visited_today: str = "Done"
    done_at: datetime


class BatchSettingsOut(BaseModel):
    rollover_hour: int
    rollover_timezone: str | None = None

    class Config:
        from_attributes = True


class BatchSettingsUpdate(BaseModel):
    rollover_hour: int
    rollover_timezone: str | None = None
