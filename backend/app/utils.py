# app/utils.py
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import urllib.request
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Any, Dict, Optional, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .models import Task, TaskEvent, TaskEventType, User, Student, TaskStatus


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


# ---------------- Task creation helper (Home Visite) ----------------


def create_home_visit_task_for_student(
    db: Session,
    *,
    student: Student,
    actor: User,
    body: str | None = None,
    assignee_user_id: int | None = None,
    due_at: datetime | None = None,
    external_ref: str | None = None,
    checklist: List[dict] | None = None,
    # snapshot-felter – ikke kolonner i Task, men vi kan henge dem på objektet
    attendance_pct: int | None = None,
    last_absence_date: date | None = None,
    last_absence_reason: str | None = None,
    visit_notes: str | None = None,
) -> Task:
    """
    Felles logikk for å opprette en 'Home Visite'-task for en elev.

    Brukes både fra /api/batch/import_students, /api/tasks og seed.py.

    - Tittel: alltid "Fornavn Etternavn" hvis mulig, ellers student.name
    - Body/reason: innkommende body hvis satt, ellers "Home Visite"
    - Assignee: innkommende assignee_user_id, ellers actor (typisk admin)
    - due_at: innkommende due_at, ellers datetime.utcnow()
    - status: alltid NEW ved opprettelse
    """

    # 1) Tittel: "FirstName LastName" hvis vi har det, ellers student.name
    if getattr(student, "first_name", None) and getattr(student, "last_name", None):
        title = f"{student.first_name} {student.last_name}"
    else:
        title = student.name

    # 2) Reason/body: bruk innkommende hvis satt, ellers "Home Visite"
    text_body = (body or "").strip()
    if not text_body:
        text_body = "Home Visite"

    # 3) Fallback assignee: hvis ingen gitt, bruk actor som assignee
    effective_assignee_id = assignee_user_id or actor.id

    # 4) due_at: hvis ikke satt, bruk nå
    effective_due_at = due_at or datetime.utcnow()

    # 5) Checklist default
    effective_checklist = checklist or []

    # Viktig: snapshot-feltene finnes ikke som kolonner på Task,
    # så de SENDES IKKE inn som keyword-arguments her.
    task = Task(
        student_id=student.id,
        title=title,
        body=text_body,
        address=student.address,
        status=TaskStatus.NEW,  # ev. TaskStatus.ASSIGNED hvis du vil ha det som default
        assignee_user_id=effective_assignee_id,
        created_by=actor.id,
        due_at=effective_due_at,
        checklist=effective_checklist,
        external_ref=external_ref,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    # Snapshot-feltene kan henges på objektet i minnet hvis du vil bruke dem i responses
    if attendance_pct is not None:
        setattr(task, "attendance_pct", attendance_pct)
    if last_absence_date is not None:
        setattr(task, "last_absence_date", last_absence_date)
    if last_absence_reason is not None:
        setattr(task, "last_absence_reason", last_absence_reason)
    if visit_notes is not None:
        setattr(task, "visit_notes", visit_notes)

    return task
