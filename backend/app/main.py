from __future__ import annotations

import os
import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.config import settings
from app.db import Base, engine, get_db, SessionLocal
from app.models import (
    Absence,
    AppSettings,
    Comment,
    Role,
    Student,
    Task,
    TaskEventType,
    TaskStatus,
    User,
)
from app.schemas import (
    AbsenceIn,
    AbsenceOut,
    AssignIn,
    BatchSettingsOut,
    BatchSettingsUpdate,
    CommentCreate,
    CommentOut,
    DoneExportItem,
    HistoryItem,
    StatusIn,
    StudentIn,
    StudentOut,
    TaskEdit,
    TaskEventOut,
    TaskIn,
    TaskOut,
    UserCreate,
    UserOut,
)
from app.utils import (
    hash_password,
    log_event,
    restore,
    soft_delete,
    notify_make_task_status,
)

SNAPSHOT_EXCLUDE_FIELDS = {
    "attendance_pct",
    "last_absence_date",
    "last_absence_reason",
    "visit_notes",
}

# -------------------- Auth-dependencies --------------------


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    """
    Leser Authorization-header og forventer:
      Authorization: Bearer user:<id>
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.strip()
    # Tillat både "Bearer user:1" og bare "user:1"
    if token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()

    if not token.startswith("user:"):
        raise HTTPException(status_code=401, detail="Invalid token format")

    try:
        user_id = int(token.split(":", 1)[1])
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def get_admin_user(user: User = Depends(require_admin)) -> User:
    """Brukes av batch-endepunkter – bare returner admin-brukeren."""
    return user


def get_api_token(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> Optional[str]:
    """
    For batch/integrasjoner: sjekker X-API-Token mot settings.API_TOKEN
    (kan være None i utvikling).
    """
    expected = getattr(settings, "API_TOKEN", None)
    if expected and x_api_token != expected:
        raise HTTPException(status_code=401, detail="Invalid API token")
    return x_api_token


# -------------------- Rollover scheduler (background) --------------------


async def rollover_scheduler_loop() -> None:
    """
    Kjør i bakgrunnen:
    - les rollover_hour fra AppSettings
    - når vi er på riktig time/minutt -> kjør rollover
    - sov litt og prøv igjen
    """
    await asyncio.sleep(5)
    last_run_date: Optional[date] = None

    while True:
        try:
            now = datetime.utcnow()
            today = now.date()

            # Les innstilling fra DB
            db = SessionLocal()
            try:
                s = db.query(AppSettings).get(1)
                rollover_hour = s.rollover_hour if s and s.rollover_hour is not None else 18
            finally:
                db.close()

            if (
                now.hour == rollover_hour
                and now.minute == 0
                and last_run_date != today
            ):
                db = SessionLocal()
                try:
                    actor = (
                        db.query(User)
                        .filter(User.role == Role.ADMIN)
                        .order_by(User.id.asc())
                        .first()
                    )
                    moved = _run_rollover_not_done(db, actor)
                    logging.info(
                        "Background rollover_not_done: moved %s tasks on %s (hour=%s)",
                        moved,
                        today,
                        rollover_hour,
                    )
                    last_run_date = today
                finally:
                    db.close()

                # vent et minutt så vi ikke trigger flere ganger samme minutt
                await asyncio.sleep(60)
            else:
                await asyncio.sleep(30)

        except Exception as exc:  # noqa: BLE001
            logging.exception("Error in rollover scheduler loop: %s", exc)
            await asyncio.sleep(60)


# -------------------- App + CORS --------------------


if isinstance(settings.CORS_ORIGINS, str):
    _origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
else:
    _origins = settings.CORS_ORIGINS

app = FastAPI(title="Visit Task Pro API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# where the built frontend is copied by build step
static_dir = os.path.join(os.path.dirname(__file__), "static")
assets_dir = os.path.join(static_dir, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.middleware("http")
async def no_cache_index(request: Request, call_next):
    resp: Response = await call_next(request)
    if request.url.path in ("/", "/index.html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.on_event("startup")
async def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(rollover_scheduler_loop())


# -------------------- Auth --------------------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut


@app.post("/api/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Simple email + password login.

    Returns a lightweight bearer token: "user:<id>".
    The frontend should store it and send as:
        Authorization: Bearer user:<id>
    """
    user = db.query(User).filter(User.email == data.email).first()
    from app.utils import verify_password  # lokal import

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = f"user:{user.id}"
    return LoginResponse(token=token, user=user)


# -------------------- Health / Me --------------------


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# -------------------- Comments --------------------


@app.get("/api/tasks/{task_id}/comments", response_model=List[CommentOut])
def list_comments(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    items = (
        db.query(Comment)
        .filter(Comment.task_id == task_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return items


@app.post("/api/tasks/{task_id}/comments", response_model=CommentOut)
def add_comment(
    task_id: int,
    body: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    author = user.name
    c = Comment(task_id=task_id, author=author, text=body.text.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# -------------------- Students --------------------


@app.post("/api/students", response_model=StudentOut, dependencies=[Depends(require_admin)])
def create_student(
    data: StudentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = Student(
        name=data.name,
        student_class=data.student_class,
        address=data.address,
        attendance_pct=data.attendance_pct,
        absence_pct=data.absence_pct,
        last_absence_date=data.last_absence_date,
        last_absence_reason=data.last_absence_reason,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@app.get("/api/students", response_model=List[StudentOut])
def list_students(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.query(Student).order_by(Student.name.asc()).all()


@app.get("/api/students/{student_id}/history", response_model=List[HistoryItem])
def student_history(
    student_id: int,
    days: int = 90,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(days=days)
    absences = (
        db.query(Absence)
        .filter(
            Absence.student_id == student_id,
            Absence.date >= since.date(),
        )
        .all()
    )

    items: List[HistoryItem] = []
    for a in absences:
        items.append(
            HistoryItem(
                kind="absence",
                date=datetime.combine(a.date, datetime.min.time()),
                reason_code=a.reason_code,
                note=a.note,
                reported_by=a.reported_by,
            )
        )

    visits = (
        db.query(Task)
        .filter(Task.student_id == student_id, Task.status == TaskStatus.DONE)
        .all()
    )
    for t in visits:
        items.append(
            HistoryItem(
                kind="visit",
                date=(t.completed_at or t.due_at or datetime.utcnow()),
                title=t.title,
            )
        )

    items.sort(key=lambda x: x.date, reverse=True)
    return items


# -------------------- Absences --------------------


@app.post("/api/absences", response_model=AbsenceOut)
def create_absence(
    data: AbsenceIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a = Absence(
        student_id=data.student_id,
        date=data.date,
        reason_code=data.reason_code,
        note=data.note,
        reported_by=data.reported_by,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# -------------------- Tasks --------------------


@app.post("/api/tasks", response_model=TaskOut, dependencies=[Depends(require_admin)])
def create_task(
    data: TaskIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = data.model_dump(exclude=SNAPSHOT_EXCLUDE_FIELDS, exclude_unset=True)
    t = Task(**payload, status=TaskStatus.NEW, created_by=user.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    log_event(db, t, user, TaskEventType.EDIT, {"create": True})
    return t


@app.get("/api/tasks", response_model=List[TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status: Optional[TaskStatus] = None,
    scope: Optional[str] = None,
    sort: Optional[str] = None,
    order: Optional[str] = None,
):
    q = db.query(Task).filter(Task.deleted_at.is_(None))
    if status:
        q = q.filter(Task.status == status)

    # Scope: admins kan be om 'all' (default); users default til 'my'
    if user.role != Role.ADMIN or scope == "my":
        q = q.filter((Task.assignee_user_id == user.id) | (Task.created_by == user.id))

    # Sorting
    sort = (sort or "due_at").lower()
    order = (order or "asc").lower()
    allowed = {"due_at", "updated_at", "completed_at"}
    if sort not in allowed:
        sort = "due_at"
    col = getattr(Task, sort)
    if order == "desc":
        q = q.order_by(col.is_(None), col.desc())
    else:
        q = q.order_by(col.is_(None), col.asc())
    return q.all()


@app.get("/api/tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t or t.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    if (
        user.role != Role.ADMIN
        and t.assignee_user_id != user.id
        and t.created_by != user.id
    ):
        raise HTTPException(status_code=403, detail="Forbidden")
    return t


@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def edit_task(
    task_id: int,
    data: TaskEdit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")

    payload = data.model_dump(exclude_unset=True)

    # Unify "reason" -> "body" så Edit Reason og Reject Reason deler samme felt
    if "reason" in payload and "body" not in payload:
        payload["body"] = payload.pop("reason")

    if user.role != Role.ADMIN:
        if t.assignee_user_id != user.id and t.created_by != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        allowed = {"checklist", "address", "reason", "due_at", "title", "body"}
        disallowed = set(payload.keys()) - allowed
        if disallowed:
            raise HTTPException(
                status_code=403,
                detail=f"Fields not allowed for user: {sorted(disallowed)}",
            )

    changed = {}
    for k, v in payload.items():
        setattr(t, k, v)
        changed[k] = v

    db.add(t)
    db.commit()
    db.refresh(t)
    log_event(db, t, user, TaskEventType.EDIT, {"changed": changed})
    return t


@app.delete("/api/tasks/{task_id}", dependencies=[Depends(require_admin)])
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    soft_delete(db, t, user)
    return {"ok": True}


@app.post("/api/tasks/{task_id}/restore", dependencies=[Depends(require_admin)])
def restore_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    restore(db, t, user)
    return {"ok": True}


@app.post(
    "/api/tasks/{task_id}/assign",
    response_model=TaskOut,
    dependencies=[Depends(require_admin)],
)
def assign_task(
    task_id: int,
    data: AssignIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    prev = t.assignee_user_id
    t.assignee_user_id = data.assignee_user_id
    if t.status in [TaskStatus.NEW, TaskStatus.REJECTED]:
        t.status = TaskStatus.ASSIGNED
    db.add(t)
    db.commit()
    db.refresh(t)
    evt = (
        TaskEventType.ASSIGN
        if prev is None or prev == data.assignee_user_id
        else TaskEventType.REASSIGN
    )
    log_event(db, t, user, evt, {"from": prev, "to": data.assignee_user_id})
    return t


@app.post("/api/tasks/{task_id}/status", response_model=TaskOut)
def change_status(
    task_id: int,
    data: StatusIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if user.role != Role.ADMIN and t.assignee_user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    action = data.action
    now_iso = datetime.utcnow().isoformat()
    if action == "accept":
        t.status = TaskStatus.ACCEPTED
        log_event(db, t, user, TaskEventType.ACCEPT, {"at": now_iso})
    elif action == "reject":
        if not data.reason:
            raise HTTPException(status_code=400, detail="Reason required for reject")
        t.status = TaskStatus.REJECTED
        t.body = (data.reason or "").strip()  # lagre reason i Task.body
        log_event(
            db,
            t,
            user,
            TaskEventType.REJECT,
            {"reason": data.reason, "at": now_iso},
        )
    elif action == "complete":
        t.status = TaskStatus.DONE
        t.completed_at = datetime.utcnow()
        log_event(db, t, user, TaskEventType.COMPLETE, {"at": now_iso})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    db.add(t)
    db.commit()
    db.refresh(t)

    if t.status == TaskStatus.DONE:
        # SEND DONE-TASK TIL MAKE.COM
        notify_make_task_status(t)

    return t


@app.get("/api/tasks/{task_id}/events", response_model=List[TaskEventOut])
def task_events(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if (
        user.role != Role.ADMIN
        and t.assignee_user_id != user.id
        and t.created_by != user.id
    ):
        raise HTTPException(status_code=403, detail="Forbidden")

    rows = db.execute(
        text(
            "SELECT id, task_id, type, metadata, actor_user_id, created_at "
            "FROM task_events WHERE task_id = :tid ORDER BY created_at DESC"
        ),
        {"tid": task_id},
    ).mappings().all()

    out: List[TaskEventOut] = []
    for r in rows:
        payload = {
            "id": r["id"],
            "task_id": r["task_id"],
            "type": r["type"],
            "meta": r["metadata"],
            "actor_user_id": r["actor_user_id"],
            "created_at": r["created_at"],
        }
        out.append(TaskEventOut(**payload))
    return out


# -------------------- Home-visit task logic & batch endpoints --------------------


@app.get("/api/tasks/today", response_model=List[TaskOut])
def get_todays_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[TaskOut]:
    """Return today's tasks for the logged-in field user.

    - Only tasks that are not DONE or REJECTED
    - Filtered by assignee
    - Uses due_at date as the "today" bucket.
    """
    today = datetime.utcnow().date()
    q = (
        db.query(Task)
        .filter(
            Task.deleted_at.is_(None),
            Task.assignee_user_id == user.id,
            Task.status.notin_([TaskStatus.DONE, TaskStatus.REJECTED]),
            func.date(Task.due_at) == today,
        )
        .order_by(Task.due_at.asc())
    )
    tasks = q.all()

    # Attach lightweight attendance snapshot for UI (ingen skjemamigrasjon)
    for t in tasks:
        if getattr(t, "student_id", None):
            student = db.query(Student).filter(Student.id == t.student_id).first()
            if student:
                absences = (
                    db.query(Absence)
                    .filter(Absence.student_id == student.id)
                    .order_by(Absence.date.desc())
                    .all()
                )
                last_abs = absences[0] if absences else None
                # enkel «fake» attendance hvis du vil
                t.attendance_pct = max(40, 100 - len(absences) * 5)  # type: ignore[attr-defined]
                if last_abs:
                    t.last_absence_date = last_abs.date  # type: ignore[attr-defined]
                    t.last_absence_reason = last_abs.reason_code  # type: ignore[attr-defined]
    return tasks


@app.get(
    "/api/admin/tasks",
    response_model=List[TaskOut],
    dependencies=[Depends(require_admin)],
)
def admin_tasks_overview(
    db: Session = Depends(get_db),
    date_filter: Optional[datetime] = None,
    bucket: Optional[str] = None,  # "not_done" | "rejected" | "all"
) -> List[TaskOut]:
    """Admin view: list tasks for a given date and bucket.

    - not_done: alt som ikke er DONE/REJECTED
    - rejected: bare REJECTED
    - all: ingen statusfilter
    """
    q = db.query(Task).filter(Task.deleted_at.is_(None))

    if date_filter:
        q = q.filter(func.date(Task.due_at) == date_filter.date())

    if bucket == "not_done":
        q = q.filter(Task.status.notin_([TaskStatus.DONE, TaskStatus.REJECTED]))
    elif bucket == "rejected":
        q = q.filter(Task.status == TaskStatus.REJECTED)

    return q.order_by(Task.due_at.asc()).all()


@app.post(
    "/api/tasks/{task_id}/move_to_tomorrow",
    response_model=TaskOut,
    dependencies=[Depends(require_admin)],
)
def move_task_to_tomorrow(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    """Move a task's due_at date to tomorrow.

    Used by Admin to collect "not done" tasks for tomorrow's list.
    """
    t = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")

    if not t.due_at:
        t.due_at = datetime.utcnow()

    tomorrow = t.due_at.date() + timedelta(days=1)
    t.due_at = datetime.combine(tomorrow, t.due_at.time())
    db.add(t)
    db.commit()
    db.refresh(t)

    log_event(db, t, user, TaskEventType.EDIT, {"move_to": "tomorrow"})
    return t


# -------------------- Batch endpoints (called by external scheduler) --------------------


@app.post(
    "/api/batch/import_daily",
    response_model=List[TaskOut],
    dependencies=[Depends(require_admin)],
)
def batch_import_daily(
    payload: List[TaskIn],
    db: Session = Depends(get_db),
    actor: User = Depends(get_admin_user),
    _token: Optional[str] = Depends(get_api_token),
) -> List[TaskOut]:
    """08:00-batch: create tasks from external system.

    External integration can POST an array of TaskIn objects.
    If due_at is missing we default to today at 10:00.
    """
    today = datetime.utcnow().date()
    created: List[Task] = []
    for item in payload:
        data = item.model_dump(exclude=SNAPSHOT_EXCLUDE_FIELDS, exclude_unset=True)
        if not data.get("due_at"):
            data["due_at"] = datetime.combine(today, datetime.min.time()).replace(hour=10)
        t = Task(**data, status=TaskStatus.NEW, created_by=actor.id)
        db.add(t)
        created.append(t)
    db.commit()
    for t in created:
        db.refresh(t)
    return created


@app.post(
    "/api/batch/rollover_not_done",
    dependencies=[Depends(require_admin)],
)
def batch_rollover_not_done(
    db: Session = Depends(get_db),
    actor: User = Depends(get_admin_user),
    _token: Optional[str] = Depends(get_api_token),
) -> dict:
    moved = _run_rollover_not_done(db, actor)
    return {"moved": moved}


def _run_rollover_not_done(db: Session, actor: User | None = None) -> int:
    """
    Faktisk jobb som flytter dagens ikke-ferdige tasks til i morgen.
    Brukes både av API-endepunktet og av bakgrunnsscheduler.
    """
    today = datetime.utcnow().date()
    tasks = (
        db.query(Task)
        .filter(
            Task.deleted_at.is_(None),
            func.date(Task.due_at) == today,
            Task.status.notin_([TaskStatus.DONE, TaskStatus.REJECTED]),
        )
        .all()
    )

    moved = 0
    for t in tasks:
        tomorrow = today + timedelta(days=1)
        if not t.due_at:
            t.due_at = datetime.combine(today, datetime.min.time()).replace(hour=10)
        t.due_at = datetime.combine(tomorrow, t.due_at.time())
        db.add(t)
        moved += 1

    db.commit()

    # Logg i event-tabellen hvis vi har en "actor" (admin)
    if actor and moved:
        for t in tasks:
            log_event(db, t, actor, TaskEventType.EDIT, {"batch": "rollover_not_done"})

    return moved


@app.get(
    "/api/batch/export_done",
    response_model=List[DoneExportItem],
    dependencies=[Depends(require_admin)],
)
def batch_export_done(
    date_filter: Optional[date] = None,
    db: Session = Depends(get_db),
    _token: Optional[str] = Depends(get_api_token),
) -> List[DoneExportItem]:
    """
    20:00-batch: returner DONE-oppgaver pr dag som Make.com kan bruke til
    å oppdatere Excel:

    - Matchet på Task.status == DONE
    - Kobler mot Student for å få Admission Number
    - Filtrerer på completed_at-dato == date_filter (eller i dag)
    """
    if date_filter is None:
        date_filter = datetime.utcnow().date()

    rows = (
        db.query(Task, Student)
        .join(Student, Task.student_id == Student.id)
        .filter(
            Task.deleted_at.is_(None),
            Task.status == TaskStatus.DONE,
            Task.completed_at.isnot(None),
            func.date(Task.completed_at) == date_filter,
        )
        .all()
    )

    out: List[DoneExportItem] = []
    for task, student in rows:
        if not getattr(student, "admission_number", None):
            continue

        out.append(
            DoneExportItem(
                admission_number=student.admission_number,
                done_at=task.completed_at,  # type: ignore[arg-type]
            )
        )

    return out


@app.post(
    "/api/batch/import_students",
    response_model=List[StudentOut],
    dependencies=[Depends(require_admin)],
)
def batch_import_students(
    payload: List[StudentIn],
    db: Session = Depends(get_db),
    actor: User = Depends(get_admin_user),
    _token: Optional[str] = Depends(get_api_token),
) -> List[StudentOut]:
    """
    07:00-batch: oppdater elever + opprett dagens Visit-tasks.

    - Upsert-er studentdata basert på admission_number (hvis finnes),
      ellers faller tilbake på name + year.
    - Hvis absent_today == True → lager "Visit student"-task for i dag,
      men bare hvis det ikke finnes en aktiv task for denne eleven i dag.
    """
    today = datetime.utcnow().date()
    out: List[Student] = []

    for item in payload:
        data = item.model_dump(exclude_unset=True)

        admission_number = data.get("admission_number")

        # --- Finn eksisterende student ---
        if admission_number:
            q = db.query(Student).filter(Student.admission_number == admission_number)
        else:
            full_name = f'{data.get("first_name", "").strip()} {data.get("last_name", "").strip()}'.strip()
            q = db.query(Student).filter(
                Student.name == full_name,
                Student.student_class == data.get("year"),
            )

        s = q.first()
        if not s:
            s = Student()
            if admission_number:
                s.admission_number = admission_number

        # --- Oppdater felter på student ---
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        if first_name:
            s.first_name = first_name
        if last_name:
            s.last_name = last_name
        name_combined = f"{first_name} {last_name}".strip()
        if name_combined:
            s.name = name_combined

        s.student_class = data.get("year") or s.student_class
        s.address = data.get("address") or s.address
        s.gender = data.get("gender") or s.gender

        s.contact_name = data.get("contact_name") or s.contact_name
        s.contact_relationship = data.get("contact_relationship") or s.contact_relationship
        s.contact_phone = data.get("contact_phone") or s.contact_phone

        s.absent_today = bool(data.get("absent_today", False))

        s.attendance_ytd = data.get("attendance_ytd")
        s.attendance_last_week = data.get("attendance_last_week")
        s.attendance_last_2_weeks = data.get("attendance_last_2_weeks")
        s.attendance_last_3_weeks = data.get("attendance_last_3_weeks")
        s.attendance_last_4_weeks = data.get("attendance_last_4_weeks")

        db.add(s)
        db.flush()  # sørg for at s.id har verdi

        out.append(s)

        # --- Hvis eleven er markert som absent today → lag dagens task ---
        if s.absent_today:
            existing = (
                db.query(Task)
                .filter(
                    Task.student_id == s.id,
                    Task.deleted_at.is_(None),
                    func.date(Task.due_at) == today,
                    Task.status.notin_([TaskStatus.DONE, TaskStatus.REJECTED]),
                )
                .first()
            )
            if not existing:
                # default due_at = i dag kl 10:00
                due_dt = datetime.combine(
                    today,
                    datetime.min.time(),
                ).replace(hour=10)

                t = Task(
                    student_id=s.id,
                    title="Visit student",
                    address=s.address,
                    status=TaskStatus.NEW,
                    due_at=due_dt,
                    created_by=actor.id,
                    checklist=[],
                )
                db.add(t)

    db.commit()
    for s in out:
        db.refresh(s)
    return out


# -------------------- Batch settings (admin) --------------------


@app.get(
    "/api/settings/batch",
    response_model=BatchSettingsOut,
    dependencies=[Depends(require_admin)],
)
def get_batch_settings(db: Session = Depends(get_db)):
    s = db.query(AppSettings).get(1)
    if not s:
        s = AppSettings(id=1, rollover_hour=18)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


@app.post(
    "/api/settings/batch",
    response_model=BatchSettingsOut,
    dependencies=[Depends(require_admin)],
)
def update_batch_settings(
    data: BatchSettingsUpdate,
    db: Session = Depends(get_db),
):
    if not 0 <= data.rollover_hour <= 23:
        raise HTTPException(status_code=400, detail="Hour must be between 0 and 23")

    s = db.query(AppSettings).get(1)
    if not s:
        s = AppSettings(id=1)
        db.add(s)

    s.rollover_hour = data.rollover_hour
    db.commit()
    db.refresh(s)
    return s


# -------------------- Users & admin helpers --------------------


@app.get("/api/users", response_model=List[UserOut], dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id.asc()).all()


@app.post("/api/users", response_model=UserOut, dependencies=[Depends(require_admin)])
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")
    u = User(
        name=data.name,
        email=data.email,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@app.delete("/api/users/{user_id}", dependencies=[Depends(require_admin)])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    # protect demo seed users
    if u.id in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Cannot delete demo user")
    db.delete(u)
    db.commit()
    return {"ok": True}


@app.delete("/api/students/{student_id}", dependencies=[Depends(require_admin)])
def delete_student(student_id: int, db: Session = Depends(get_db)):
    s = db.query(Student).filter(Student.id == student_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    # avoid breaking FK constraints if det finnes history
    has_tasks = db.query(Task).filter(Task.student_id == student_id).count()
    has_absences = db.query(Absence).filter(Absence.student_id == student_id).count()
    if has_tasks or has_absences:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete student with existing tasks or absences",
        )
    db.delete(s)
    db.commit()
    return {"ok": True}


# -------------------- SPA fallback (last) --------------------


@app.head("/")
def head_root():
    return Response(status_code=200)


@app.get("/{full_path:path}")
def spa_fallback(full_path: str, request: Request):
    # La mountede routes (/assets, /api, docs) ha prioritet; dette er siste utvei.
    if os.path.isdir(static_dir):
        return FileResponse(os.path.join(static_dir, "index.html"))
    raise HTTPException(status_code=404)
