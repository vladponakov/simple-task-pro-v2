from pydantic import BaseModel
from typing import Optional, List, Literal, Any
from datetime import datetime, date
from .models import TaskStatus, TaskEventType, Role
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class CommentCreate(BaseModel):
    text: str

class CommentOut(BaseModel):
    id: int
    author: Optional[str] = None
    text: str
    created_at: datetime
    class Config: orm_mode = True

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    address: Optional[str] = None
    due_at: Optional[datetime] = None
    reason: Optional[str] = None
    checklist: Optional[list] = None
    assignee_user_id: Optional[int] = None
    status: Optional[str] = None

class UserOut(BaseModel):
    id: int
    name: str
    role: Role
    class Config:
        from_attributes = True

class StudentIn(BaseModel):
    name: str
    student_class: Optional[str] = None
    address: Optional[str] = None

class StudentOut(StudentIn):
    id: int
    class Config:
        from_attributes = True

class AbsenceIn(BaseModel):
    student_id: int
    date: date
    reason_code: Literal["Syk", "Reise", "Annet"]
    note: Optional[str] = None
    reported_by: str

class AbsenceOut(AbsenceIn):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class ChecklistItem(BaseModel):
    text: str
    done: bool = False

class TaskIn(BaseModel):
    student_id: int
    title: str
    body: Optional[str] = None
    address: Optional[str] = None
    checklist: Optional[List[ChecklistItem]] = None
    due_at: Optional[datetime] = None
    assignee_user_id: Optional[int] = None

class TaskOut(TaskIn):
    id: int
    status: TaskStatus
    created_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class TaskEdit(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    address: Optional[str] = None
    checklist: Optional[List[ChecklistItem]] = None
    due_at: Optional[datetime] = None
    student_id: Optional[int] = None

class AssignIn(BaseModel):
    assignee_user_id: int

class StatusIn(BaseModel):
    action: Literal["accept", "reject", "complete"]
    reason: Optional[str] = None

class TaskEventOut(BaseModel):
    id: int
    task_id: int
    type: TaskEventType
    metadata: Optional[Any] = None
    actor_user_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class HistoryItem(BaseModel):
    kind: Literal["absence", "visit"]
    date: datetime
    title: Optional[str] = None
    reason_code: Optional[str] = None
    note: Optional[str] = None
    reported_by: Optional[str] = None
