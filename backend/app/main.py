from __future__ import annotations

import os
import asyncio
import logging
from datetime import datetime, timedelta, date
import pytz
from pytz import UnknownTimeZoneError
from typing import List, Optional, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.responses import Response
from starlette.middleware.sessions import SessionMiddleware
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
    StudentCreate,
    TaskEdit,
    TaskEventOut,
    TaskIn,
    TaskOut,
    UserCreate,
    UserOut,
    UserUpdate,  
    MeUpdate,
)
from app.utils import (
    hash_password,
    log_event,
    restore,
    soft_delete,
    notify_make_task_status,
    create_home_visit_task_for_student,
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


def _get_local_today_and_tz(rollover_tz_name: str) -> tuple[date, str]:
    """
    Returnerer (today_in_tz, tz_name_used) basert på valgt timezone.
    Faller tilbake til UTC hvis tz ikke finnes.
    """
    try:
        tz = pytz.timezone(rollover_tz_name)
    except UnknownTimeZoneError:
        logging.warning(
            "Unknown timezone %s, falling back to UTC in _get_local_today_and_tz",
            rollover_tz_name,
        )
        tz = pytz.UTC
        rollover_tz_name = "UTC"

    now_tz = datetime.now(tz)
    return now_tz.date(), rollover_tz_name


# -------------------- Rollover scheduler (background) --------------------


async def rollover_scheduler_loop() -> None:
    """
    Bakgrunnsjobb som:
    - Leser rollover_hour + rollover_timezone fra AppSettings
    - Bruker valgt timezone (f.eks. Europe/Oslo eller Europe/London)
    - Kjører _run_rollover_not_done én gang per (dag + time + timezone)
    """
    # gi appen litt tid til å starte
    await asyncio.sleep(5)
    last_run_key: Optional[str] = None  # f.eks. "2025-11-30-18-Europe/Oslo"

    while True:
        try:
            # 1) Les config fra DB
            db = SessionLocal()
            try:
                s = db.query(AppSettings).get(1)
                rollover_hour = (
                    s.rollover_hour if s and s.rollover_hour is not None else 18
                )
                rollover_tz_name = (
                    s.rollover_timezone or "Europe/London"
                    if s
                    else "Europe/London"
                )
            finally:
                db.close()

            # 2) Finn "i dag" i valgt timezone (pytz-basert)
            today_tz, tz_name_used = _get_local_today_and_tz(rollover_tz_name)

            # unik nøkkel per dag + time + timezone
            current_key = f"{today_tz.isoformat()}-{rollover_hour}-{tz_name_used}"

            # 3) Sjekk lokal tid i valgt timezone
            try:
                tz = pytz.timezone(tz_name_used)
            except UnknownTimeZoneError:
                tz = pytz.UTC
                tz_name_used = "UTC"

            now_local = datetime.now(tz)
            local_hour = now_local.hour
            local_minute = now_local.minute

            if (
                local_hour == rollover_hour
                and local_minute == 0
                and last_run_key != current_key
            ):
                db = SessionLocal()
                try:
                    actor = (
                        db.query(User)
                        .filter(User.role == Role.ADMIN)
                        .order_by(User.id.asc())
                        .first()
                    )
                    moved = _run_rollover_not_done(db, actor, today=today_tz)
                    logging.info(
                        "Background rollover_not_done: moved %s tasks on %s (hour=%s, tz=%s)",
                        moved,
                        today_tz,
                        rollover_hour,
                        tz_name_used,
                    )
                    last_run_key = current_key
                finally:
                    db.close()

                # vent et minutt så vi ikke trigger flere ganger samme minutt
                await asyncio.sleep(60)
            else:
                await asyncio.sleep(30)

        except Exception as exc:  # noqa: BLE001
            logging.exception("Error in rollover scheduler loop: %s", exc)
            await asyncio.sleep(60)


import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.config import Config as StarletteConfig
from authlib.integrations.starlette_client import OAuth

from .config import settings

# -------------------- App + CORS --------------------

# CORS_ORIGINS kan komme som liste (standard) eller som string via env
if isinstance(settings.CORS_ORIGINS, str):
    _origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
else:
    _origins = settings.CORS_ORIGINS

app = FastAPI(title="Visit Task Pro API v2")

# ---- Google OAuth client ----
_starlette_config = StarletteConfig(environ=os.environ)
oauth = OAuth(_starlette_config)

if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
else:
    print(
        "WARNING: Google OAuth is not fully configured – "
        "GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is missing"
    )

print(
    "GOOGLE OAUTH CONFIG:",
    bool(settings.GOOGLE_CLIENT_ID),
    bool(settings.GOOGLE_CLIENT_SECRET),
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Sessions – nødvendig for Google OAuth (request.session)
app.add_middleware(
    SessionMiddleware,
    secret_key="super-secret-session-key-change-me",
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

# -------------------- Auth --------------------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@app.get("/api/auth/google/start")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/api/auth/google/callback", name="google_auth_callback")
async def google_auth_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    """Callback fra Google – logger inn / lager bruker og skriver til localStorage."""
    try:
        # 1) Hent token + userinfo fra Google
        token = await oauth.google.authorize_access_token(request)
        print("GOOGLE TOKEN:", token)

        userinfo = token.get("userinfo") or {}
        print("GOOGLE USERINFO:", userinfo)

        email = (userinfo.get("email") or "").lower()
        if not email:
            raise HTTPException(status_code=400, detail="No email from Google")

        # 2) Eventuell domenesjekk (ikke aktiv nå siden GOOGLE_ALLOWED_HD er tom/None)
        if settings.GOOGLE_ALLOWED_HD:
            hd = userinfo.get("hd")  # hosted domain
            if hd != settings.GOOGLE_ALLOWED_HD:
                raise HTTPException(status_code=403, detail="Google account not allowed")

        # 3) Finn eller opprett bruker
        user = db.query(User).filter(User.email == email).first()

        if not user:
            # Bruk navnet fra Google eller e-posten
            name = userinfo.get("name") or email
            user = User(
                name=name,
                email=email,
                role=Role.USER,
                password_hash=hash_password(os.urandom(16).hex()),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print("GOOGLE: created new user", user.id, user.email)
        else:
            print("GOOGLE: existing user", user.id, user.email)

        # 4) Lag token i samme format som /api/login
        api_token = f"user:{user.id}"

        # 5) HTML som kjører i browseren, setter localStorage og redirecter til "/"
        html = f"""
        <html><body>
        <script>
          const token = "{api_token}";
          const user = {{
            id: {user.id},
            name: "{user.name}",
            email: "{user.email}",
            role: "{user.role.value}"
          }};

          localStorage.setItem("auth_token", token);
          localStorage.setItem("current_user", JSON.stringify(user));
          localStorage.setItem("x_user", user.email);

          window.location.replace("/");
        </script>
        Logging you in with Google...
        </body></html>
        """
        return HTMLResponse(content=html)

    except HTTPException:
        # HTTPExceptions lar vi gå igjennom som normalt
        raise
    except Exception as e:
        # Alt annet – logg og returner 500 med feilmelding
        print("GOOGLE CALLBACK ERROR:", repr(e))
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error in Google callback: {e}",
        )


@app.post("/api/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    Superenkel login:
    - Slår opp bruker på e-post
    - Verifiserer passord
    - Returnerer token + bruker som ren dict
    """
    from app.utils import verify_password  # lokal import for å unngå sirkulær import

    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        # Viktig: 401 ved feil innlogging, ikke 500
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = f"user:{user.id}"

    # Bygg JSON manuelt – ingen komplisert pydantic-nesting
    return {
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        },
    }


# -------------------- Health / Me --------------------


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@app.patch("/api/me", response_model=UserOut)
def update_me(
    data: MeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if data.start_address is not None:
        s = data.start_address.strip()
        user.start_address = s or None

    db.commit()
    db.refresh(user)
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

@app.post(
    "/api/students",
    response_model=StudentOut,
    dependencies=[Depends(require_admin)],
)
def create_student(
    data: StudentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = Student(
        name=data.name.strip(),
        student_class=data.student_class.strip() if data.student_class else None,
        address=data.address.strip() if data.address else None,
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

@app.post(
    "/api/tasks",
    response_model=TaskOut,
)
def create_task(
    data: TaskIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 1) Finn studenten
    student = db.query(Student).filter(Student.id == data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # 2) Bestem hvem tasken skal assignes til
    if user.role == Role.ADMIN:
        # Admin kan velge fri assignee fra payload
        effective_assignee = data.assignee_user_id
    else:
        # Vanlig bruker: alltid til seg selv, ignorerer ev. assignee i payload
        effective_assignee = user.id

    # 3) Opprett task via felles helper
    t = create_home_visit_task_for_student(
        db,
        student=student,
        actor=user,  # den innloggede (admin eller bruker)
        body=data.body,  # reason
        assignee_user_id=effective_assignee,
        due_at=data.due_at,        # hvis tom → helper setter standard (10:00)
        external_ref=data.external_ref,
        checklist=data.checklist,
        attendance_pct=data.attendance_pct,
        last_absence_date=data.last_absence_date,
        last_absence_reason=data.last_absence_reason,
        visit_notes=data.visit_notes,
    )

    # 4) Logg event
    log_event(db, t, user, TaskEventType.EDIT, {"create": True})
    return t

@app.patch(
    "/api/users/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_admin)],
)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    # Endre navn
    if data.name is not None:
        s = data.name.strip()
        if s:
            u.name = s

    # Endre rolle (User/Admin)
    if data.role is not None:
        u.role = data.role

    # Endre start_address
    if data.start_address is not None:
        s = data.start_address.strip()
        u.start_address = s or None

    # Endre passord
    if data.password is not None:
        u.password_hash = hash_password(data.password)

    db.commit()
    db.refresh(u)
    return u

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

    # Bygg payload ut fra det som faktisk er sendt inn
    payload = data.model_dump(exclude_unset=True)

    # Unify "reason" -> "body" så Edit Reason og Reject Reason deler samme felt
    if "reason" in payload and "body" not in payload:
        payload["body"] = payload.pop("reason")

    # Ikke-admin har begrenset hva de kan endre
    if user.role != Role.ADMIN:
        # Må være assignee eller creator
        if t.assignee_user_id != user.id and t.created_by != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Fjern felter som vanlige brukere aldri får lov til å tukle med
        for blocked in ("assignee_user_id", "external_ref", "status", "created_by"):
            payload.pop(blocked, None)

        # Disse feltene er lov for vanlige brukere
        allowed = {"checklist", "address", "body", "due_at", "title"}
        disallowed = set(payload.keys()) - allowed
        if disallowed:
            raise HTTPException(
                status_code=403,
                detail=f"Fields not allowed for user: {sorted(disallowed)}",
            )

    # --- Track endringer ---
    prev_assignee = t.assignee_user_id
    changed: dict[str, Any] = {}

    for k, v in payload.items():
        setattr(t, k, v)
        changed[k] = v

    # --- Hvis admin endrer assignee via Edit/Save, speil /assign-logikken ---
    if "assignee_user_id" in payload and user.role == Role.ADMIN:
        new_assignee = payload["assignee_user_id"]

        if t.status in [TaskStatus.NEW, TaskStatus.REJECTED]:
            t.status = TaskStatus.ASSIGNED
            changed["status"] = t.status

        evt = (
            TaskEventType.ASSIGN
            if prev_assignee is None or prev_assignee == new_assignee
            else TaskEventType.REASSIGN
        )
        log_event(
            db,
            t,
            user,
            evt,
            {"from": prev_assignee, "to": new_assignee},
        )

    db.add(t)
    db.commit()
    db.refresh(t)

    # Logg generell EDIT hvis noe faktisk ble endret
    if changed:
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
    """
    Manuell trigger (fra Make.com / admin) av rollover.
    Bruker samme timezone-logikk som scheduleren.
    """
    s = db.query(AppSettings).get(1)
    rollover_tz_name = (
        s.rollover_timezone or "Europe/London"
        if s
        else "Europe/London"
    )

    today_tz, tz_name_used = _get_local_today_and_tz(rollover_tz_name)
    moved = _run_rollover_not_done(db, actor, today=today_tz)
    logging.info(
        "Manual batch rollover_not_done: moved %s tasks on %s (tz=%s)",
        moved,
        today_tz,
        tz_name_used,
    )
    return {"moved": moved}


def _run_rollover_not_done(
    db: Session,
    actor: User | None = None,
    today: Optional[date] = None,
) -> int:
    """
    Faktisk jobb som flytter dagens ikke-ferdige tasks til i morgen.
    Brukes både av API-endepunktet og av bakgrunnsscheduler.

    :param today: dato i valgt timezone (hvis None -> UTC-dato).
    """
    if today is None:
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
    tomorrow = today + timedelta(days=1)

    for t in tasks:
        if not t.due_at:
            # fallback: sett til i dag kl 10:00 før vi flytter
            t.due_at = datetime.combine(today, datetime.min.time()).replace(hour=10)
        # Behold tidspunkt på dagen, bare flytt dato til i morgen
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

                # Bruk felles helper:
                # - tittel = "FirstName LastName"
                # - body = "Home Visite"
                # - assignee = actor (admin) som fallback
                # - status = NEW
                create_home_visit_task_for_student(
                    db,
                    student=s,
                    actor=actor,              # admin som kjører batch’en
                    body=None,                # lar helper sette "Home Visite"
                    assignee_user_id=None,    # lar helper bruke actor.id (admin)
                    due_at=due_dt,
                    external_ref=s.admission_number,
                    checklist=[],
                    # snapshot-felter kan fylles senere ved behov
                )

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
        # default: 18:00 London-tid
        s = AppSettings(id=1, rollover_hour=18, rollover_timezone="Europe/London")
        db.add(s)
        db.commit()
        db.refresh(s)

    # fallback hvis gamle rader mangler timezone
    if not s.rollover_timezone:
        s.rollover_timezone = "Europe/London"

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
    s.rollover_timezone = data.rollover_timezone or s.rollover_timezone or "Europe/London"

    db.commit()
    db.refresh(s)
    return s


# -------------------- Users & admin helpers --------------------


@app.get(
    "/api/users",
    response_model=List[UserOut],
    dependencies=[Depends(require_admin)],
)
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id.asc()).all()


@app.post(
    "/api/users",
    response_model=UserOut,
    dependencies=[Depends(require_admin)],
)
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

    # ❌ aldri tillat å slette admin-brukere
    if u.role == Role.ADMIN:
        raise HTTPException(status_code=400, detail="Cannot delete admin user")

    # protect demo seed users (1,2,3)
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
