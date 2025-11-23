# app/utils.py
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import urllib.request
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .models import Task, TaskEvent, TaskEventType, User


# ---------------- Password helpers ----------------


def hash_password(password: str) -> str:
    """Create a salted SHA256 hash.

    Ikke like sterkt som bcrypt/argon2, men holder fint for demo
    og krever ingen ekstra pakker.
    """
    password = password or ""
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    check = hashlib.sha256((salt + (password or "")).encode("utf-8")).hexdigest()
    return secrets.compare_digest(check, digest)


# ---------------- JSON sanitizer ----------------


def _jsonify(obj: Any) -> Any:
    """Gjør metadata JSON-vennlig (brukes i TaskEvent.meta)."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonify(v) for v in obj]
    # fallback
    return str(obj)


# ---------------- Event logging ----------------


def log_event(
    db: Session,
    task: Task,
    actor: User,
    event_type: TaskEventType,
    meta: Optional[Dict[str, Any]] = None,
) -> TaskEvent:
    ev = TaskEvent(
        task_id=task.id,
        type=event_type,
        meta=_jsonify(meta or {}),
        actor_user_id=actor.id,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


# ---------------- Soft delete / restore ----------------


def soft_delete(db: Session, task: Task, actor: User) -> None:
    if task.deleted_at is not None:
        return
    task.deleted_at = datetime.utcnow()
    db.add(task)
    db.commit()
    log_event(
        db,
        task,
        actor,
        TaskEventType.DELETE,
        {"deleted_at": task.deleted_at.isoformat()},
    )


def restore(db: Session, task: Task, actor: User) -> None:
    if task.deleted_at is None:
        return
    delta = datetime.utcnow() - task.deleted_at
    if delta > timedelta(hours=settings.RESTORE_WINDOW_HOURS):
        raise HTTPException(status_code=400, detail="Restore window expired")
    task.deleted_at = None
    db.add(task)
    db.commit()
    log_event(
        db,
        task,
        actor,
        TaskEventType.RESTORE,
        {"restored_at": datetime.utcnow().isoformat()},
    )


# ---------------- Notify Make.com when task is DONE ----------------


def notify_make_task_status(task: Task) -> None:
    """
    Kalles når en oppgave går til DONE.
    Sender et POST-kall til Make.com webhook med
    samme struktur som du brukte i curl-eksempelet.
    """
    url = settings.MAKE_WEBHOOK_URL
    api_key = settings.MAKE_WEBHOOK_API_KEY

    if not url or not api_key:
        # Ikke konfigurert → bare logg og returner stille
        logging.debug("Make.com webhook ikke konfigurert – hopper over notify.")
        return

    try:
        updated_at = task.updated_at or datetime.utcnow()

        payload: Dict[str, Any] = {
            "task_id": task.id,
            "status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "updated_at": updated_at.isoformat(),
            "task": {
                "id": task.id,
                "student_id": task.student_id,
                "title": task.title,
                "address": task.address,
                "body": task.body,
                "assignee_user_id": task.assignee_user_id,
                "status": task.status.value if hasattr(task.status, "value") else str(task.status),
                "updated_at": updated_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "external_ref": task.external_ref,
                "checklist": task.checklist or [],
            },
        }

        data_bytes = json.dumps(payload, default=str).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data_bytes,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-make-apikey": api_key,
            },
        )

        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            # Vi bryr oss ikke om body, men vi kan logge status for debugging
            logging.info("Sent DONE-task %s to Make.com, status=%s", task.id, resp.status)

    except Exception as exc:  # noqa: BLE001
        # Viktig: aldri knekke API-et selv om Make.com er nede.
        logging.exception("Failed to notify Make.com for task %s: %s", task.id, exc)
