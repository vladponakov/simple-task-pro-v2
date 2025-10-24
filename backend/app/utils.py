from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException
from .models import Task, TaskEvent, TaskEventType, User
from .config import settings

def log_event(db: Session, task: Task, actor: User, event_type: TaskEventType, metadata: dict | None = None):
    e = TaskEvent(task_id=task.id, type=event_type, meta=(metadata or {}), actor_user_id=actor.id)
    db.add(e)
    db.commit()

def soft_delete(db: Session, task: Task, actor: User):
    if task.deleted_at is not None:
        return
    task.deleted_at = datetime.utcnow()
    db.add(task); db.commit()
    log_event(db, task, actor, TaskEventType.DELETE, {"deleted_at": task.deleted_at.isoformat()})

def restore(db: Session, task: Task, actor: User):
    if task.deleted_at is None:
        return
    delta = datetime.utcnow() - task.deleted_at
    if delta > timedelta(hours=settings.RESTORE_WINDOW_HOURS):
        raise HTTPException(status_code=400, detail="Restore window expired")
    task.deleted_at = None
    db.add(task); db.commit()
    log_event(db, task, actor, TaskEventType.RESTORE, {"restored_at": datetime.utcnow().isoformat()})
