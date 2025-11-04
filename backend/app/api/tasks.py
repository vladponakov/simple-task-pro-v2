# ================================================================
# BLOCK: TASKS_ROUTER
# Purpose: Tasks CRUD, status changes, assign, and comments
# ================================================================
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Task, TaskComment
from ..schemas import (
    TaskCreate, TaskPatch, TaskOut,
    CommentCreate, CommentOut
)

# -----------------------------
# BLOCK: Optional webhook push
# -----------------------------
import os
try:
    import httpx  # optional; only used if MAKE_WEBHOOK_URL is set
except Exception:
    httpx = None

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL")  # optional push target


# ================================================================
# BLOCK: DB DEPENDENCY
# ================================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ================================================================
# BLOCK: Request models for JSON bodies (assign/status)
# ================================================================
from pydantic import BaseModel

class AssignIn(BaseModel):
    assignee_user_id: int

class StatusIn(BaseModel):
    action: str          # "complete" | "reject" | "restore"
    reason: Optional[str] = None


# ================================================================
# BLOCK: DTO MAPPER (Pydantic v2 validate)
# ================================================================
def _to_out(t: Task) -> TaskOut:
    return TaskOut.model_validate({
        "id": t.id,
        "student_id": t.student_id,
        "title": t.title,
        "address": t.address,
        "body": t.body,
        "due_at": t.due_at,
        "assignee_user_id": t.assignee_user_id,
        "status": t.status,
        "checklist": t.checklist or [],
        "external_ref": getattr(t, "external_ref", None),
        "created_by": t.created_by,
        "updated_at": t.updated_at,
        "completed_at": t.completed_at,
        "deleted_at": t.deleted_at,
    })


# ================================================================
# BLOCK: LIST TASKS
# ================================================================
@router.get("", response_model=List[TaskOut])
def list_tasks(
    status: Optional[str] = Query(None),
    updated_after: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Task).filter(Task.deleted_at.is_(None))
    if status:
        q = q.filter(Task.status == status)
    if updated_after:
        q = q.filter(Task.updated_at >= updated_after)

    q = q.order_by(Task.due_at.is_(None), Task.due_at.asc())
    rows = q.all()
    return [_to_out(t) for t in rows]


# ================================================================
# BLOCK: CREATE TASK
# ================================================================
@router.post("", response_model=TaskOut)
def create_task(payload: TaskCreate, request: Request, db: Session = Depends(get_db)):
    t = Task(
        student_id=payload.student_id,
        title=payload.title,
        address=payload.address,
        body=payload.body,
        due_at=payload.due_at,
        assignee_user_id=payload.assignee_user_id,
        status=payload.status or "New",
        checklist=[i.model_dump() for i in (payload.checklist or [])],
        external_ref=payload.external_ref,
        created_by=None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_out(t)


# ================================================================
# BLOCK: PATCH TASK
# ================================================================
@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(task_id: int, payload: TaskPatch, db: Session = Depends(get_db)):
    t: Optional[Task] = db.query(Task).get(task_id)
    if not t or t.deleted_at:
        raise HTTPException(404, "Task not found")

    if payload.title is not None:
        t.title = payload.title
    if payload.address is not None:
        t.address = payload.address
    if payload.reason is not None:
        t.body = payload.reason
    if payload.due_at is not None:
        t.due_at = payload.due_at
    if payload.assignee_user_id is not None:
        t.assignee_user_id = payload.assignee_user_id
    if payload.checklist is not None:
        t.checklist = [i.model_dump() for i in payload.checklist]
    if payload.external_ref is not None:
        t.external_ref = payload.external_ref

    db.commit()
    db.refresh(t)
    return _to_out(t)


# ================================================================
# BLOCK: DELETE TASK (soft delete)
# ================================================================
@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    t: Optional[Task] = db.query(Task).get(task_id)
    if not t or t.deleted_at:
        raise HTTPException(404, "Task not found")
    t.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


# ================================================================
# BLOCK: ASSIGN (expects JSON body)
# ================================================================
@router.post("/{task_id}/assign")
def assign(task_id: int, payload: AssignIn, db: Session = Depends(get_db)):
    t: Optional[Task] = db.query(Task).get(task_id)
    if not t or t.deleted_at:
        raise HTTPException(404, "Task not found")
    t.assignee_user_id = payload.assignee_user_id
    if t.status == "New":
        t.status = "Assigned"
    db.commit()
    return {"ok": True}


# ================================================================
# BLOCK: STATUS CHANGES (expects JSON body)
# ================================================================
@router.post("/{task_id}/status")
def set_status(task_id: int, payload: StatusIn, db: Session = Depends(get_db)):
    t: Optional[Task] = db.query(Task).get(task_id)
    if not t or t.deleted_at:
        raise HTTPException(404, "Task not found")

    action = payload.action
    reason = payload.reason

    if action == "complete":
        t.status = "Done"
        t.completed_at = datetime.utcnow()
        db.commit()

        if MAKE_WEBHOOK_URL and httpx:
            try:
                with httpx.Client(timeout=5.0) as client:
                    client.post(MAKE_WEBHOOK_URL, json={
                        "task_id": t.id,
                        "status": t.status,
                        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                        "external_ref": getattr(t, "external_ref", None),
                    })
            except Exception as e:
                logger.warning("Webhook push failed: %s", e)

        return {"ok": True}

    if action == "reject":
        t.status = "Rejected"
        if reason:
            t.body = reason
        db.commit()
        return {"ok": True}

    if action == "restore":
        t.status = "Assigned"
        db.commit()
        return {"ok": True}

    raise HTTPException(400, "Unknown action")


# ================================================================
# BLOCK: COMMENTS
# ================================================================
@router.get("/{task_id}/comments", response_model=List[CommentOut])
def list_comments(task_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(TaskComment)
        .filter(TaskComment.task_id == task_id)
        .order_by(TaskComment.id.asc())
        .all()
    )
    return rows


@router.post("/{task_id}/comments", response_model=CommentOut)
def add_comment(task_id: int, payload: CommentCreate, db: Session = Depends(get_db)):
    t: Optional[Task] = db.query(Task).get(task_id)
    if not t or t.deleted_at:
        raise HTTPException(404, "Task not found")

    c = TaskComment(task_id=task_id, author="User", text=payload.text)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c
