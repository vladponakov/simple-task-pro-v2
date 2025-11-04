# ================================================================
# BLOCK: SCHEMAS
# Purpose: Pydantic models aligning with new models & routers
# ================================================================
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field

# ---- Comments ----
class CommentCreate(BaseModel):
    text: str

class CommentOut(BaseModel):
    id: int
    author: Optional[str] = None
    text: str
    created_at: datetime
    class Config:
        from_attributes = True

# ---- Tasks ----
class ChecklistItem(BaseModel):
    text: str
    done: bool = False

class TaskCreate(BaseModel):
    student_id: int
    title: str
    address: Optional[str] = None
    body: Optional[str] = None
    due_at: Optional[datetime] = None
    assignee_user_id: Optional[int] = None
    status: Optional[Literal["New","Assigned","Rejected","Done"]] = "New"
    checklist: List[ChecklistItem] = Field(default_factory=list)
    external_ref: Optional[str] = None

class TaskPatch(BaseModel):
    title: Optional[str] = None
    address: Optional[str] = None
    reason: Optional[str] = None  # maps to body
    due_at: Optional[datetime] = None
    assignee_user_id: Optional[int] = None
    checklist: Optional[List[ChecklistItem]] = None
    external_ref: Optional[str] = None

class TaskOut(BaseModel):
    id: int
    student_id: int
    title: str
    address: Optional[str]
    body: Optional[str]
    due_at: Optional[datetime]
    assignee_user_id: Optional[int]
    status: str
    checklist: List[ChecklistItem] = []
    external_ref: Optional[str]
    created_by: Optional[int]
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]
    deleted_at: Optional[datetime]
    class Config:
        from_attributes = True

# ---- Students ----
class StudentCreate(BaseModel):
    name: str

class StudentOut(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

# ---- Users ----
class UserCreate(BaseModel):
    email: str
    name: str

class UserOut(BaseModel):
    id: int
    email: str | None
    name: str
    role: str
    class Config:
        from_attributes = True
