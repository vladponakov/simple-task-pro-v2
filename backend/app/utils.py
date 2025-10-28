# app/utils.py
from __future__ import annotations

from datetime import datetime, date, timedelta
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .models import Task, TaskEvent, TaskEventType, User


# --- JSON sanitizer for event metadata --------------------------------------
def _jsonify(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [_jsonify(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    return obj


# --- Event logging -----------------------------------------------------------
def log_event(
    db: Session,
    task: Task,
    actor: User,
    event_type: TaskEventType,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert a row into task_events with JSON-serializable metadata."""
    evt = TaskEvent(
        task_id=task.id,
        type=event_type,
        metadata=_jsonify(metadata or {}),  # <-- ensure JSON-safe
        actor_user_id=actor.id,
    )
    db.add(evt)
    db.commit()


# --- Soft delete / restore ---------------------------------------------------
def soft_delete(db: Session, task: Task, actor: User) -> None:
    if task.deleted_at is not None:
        return
    task.deleted_at = datetime.utcnow()
    db.add(task)
    db.commit()
    log_event(db, task, actor, TaskEventType.DELETE, {"deleted_at": task.deleted_at})


def restore(db: Session, task: Task, actor: User) -> None:
    if task.deleted_at is None:
        return
    delta = datetime.utcnow() - task.deleted_at
    if delta > timedelta(hours=settings.RESTORE_WINDOW_HOURS):
        raise HTTPException(status_code=400, detail="Restore window expired")
    task.deleted_at = None
    db.add(task)
    db.commit()
    log_event(db, task, actor, TaskEventType.RESTORE, {"restored_at": datetime.utcnow()})
