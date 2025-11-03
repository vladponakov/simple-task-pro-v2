# --- imports (excerpt) ---
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
import os

from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.config import settings
from app.db import Base, engine, get_db
from app.models import Task, TaskStatus, TaskEventType, User, Student, Absence, Role, Comment
from app.schemas import (
    UserOut, TaskIn, TaskOut, TaskEdit, AssignIn, StatusIn, TaskEventOut,
    AbsenceIn, AbsenceOut, StudentIn, StudentOut, HistoryItem,
    CommentCreate, CommentOut
)
from app.deps import get_current_user, require_admin, require_api_token, get_admin_user
from app.utils import log_event, soft_delete, restore

app = FastAPI()

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(static_dir, "index.html"))

# CORS only needed if frontend is on a different origin
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://<your-static-site>.onrender.com"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*", "X-User"],
# )

@app.get("/healthz")
def healthz():
    return {"ok": True}

# Tillat lokalt UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173","https://demo-taskpro.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-User"],
)

# Opprett tabeller ved oppstart (idempotent)
@app.on_event("startup")
def _on_startup():
    Base.metadata.create_all(bind=engine)

# --- Ingest (token/bypass) ---------------------------------------------------
@app.post("/api/ingest/task", response_model=TaskOut, dependencies=[Depends(require_api_token)])
def ingest_task(payload: TaskIn, db: Session = Depends(get_db), actor: User = Depends(get_admin_user)):
    t = Task(**payload.model_dump(), status=TaskStatus.NEW, created_by=actor.id)
    db.add(t); db.commit(); db.refresh(t)
    log_event(db, t, actor, TaskEventType.EDIT, {"create": True, "source": "api-token"})
    return t

@app.post("/api/ingest/tasks", response_model=List[TaskOut], dependencies=[Depends(require_api_token)])
def ingest_tasks(payload: List[TaskIn], db: Session = Depends(get_db), actor: User = Depends(get_admin_user)):
    out = []
    for item in payload:
        t = Task(**item.model_dump(), status=TaskStatus.NEW, created_by=actor.id)
        db.add(t); out.append(t)
    db.commit()
    for t in out:
        log_event(db, t, actor, TaskEventType.EDIT, {"create": True, "source": "api-token"})
    return out

# --- Health / Me -------------------------------------------------------------

@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user

# --- Comments ---------------------------------------------------------------

@app.get("/api/tasks/{task_id}/comments", response_model=List[CommentOut])
def list_comments(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    items = (
        db.query(Comment)
        .filter(Comment.task_id == task_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return items

@app.post("/api/tasks/{task_id}/comments", response_model=CommentOut)
def add_comment(task_id: int, body: CommentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    author = user.name
    c = Comment(task_id=task_id, author=author, text=body.text.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

# --- Students ---------------------------------------------------------------

@app.post("/api/students", response_model=StudentOut, dependencies=[Depends(require_admin)])
def create_student(data: StudentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = Student(name=data.name, student_class=data.student_class, address=data.address)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@app.get("/api/students", response_model=List[StudentOut])
def list_students(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Student).all()

@app.get("/api/students/{student_id}/history", response_model=List[HistoryItem])
def student_history(student_id: int, days: int = 90, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    since = datetime.utcnow() - timedelta(days=days)
    absences = db.query(Absence).filter(
        Absence.student_id == student_id,
        Absence.date >= since.date()
    ).all()

    items: List[HistoryItem] = []
    for a in absences:
        items.append(HistoryItem(
            kind="absence",
            date=datetime.combine(a.date, datetime.min.time()),
            reason_code=a.reason_code,
            note=a.note,
            reported_by=a.reported_by
        ))

    visits = db.query(Task).filter(
        Task.student_id == student_id,
        Task.status == TaskStatus.DONE
    ).all()
    for t in visits:
        items.append(HistoryItem(
            kind="visit",
            date=(t.completed_at or t.due_at or datetime.utcnow()),
            title=t.title
        ))

    items.sort(key=lambda x: x.date, reverse=True)
    return items

# --- Absences ---------------------------------------------------------------

@app.post("/api/absences", response_model=AbsenceOut)
def create_absence(data: AbsenceIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = Absence(
        student_id=data.student_id,
        date=data.date,
        reason_code=data.reason_code,
        note=data.note,
        reported_by=data.reported_by
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a

# --- Tasks ------------------------------------------------------------------

@app.post("/api/tasks", response_model=TaskOut, dependencies=[Depends(require_admin)])
def create_task(data: TaskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = Task(**data.model_dump(), status=TaskStatus.NEW, created_by=user.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    log_event(db, t, user, TaskEventType.EDIT, {"create": True})
    return t

@app.get("/api/tasks", response_model=List[TaskOut])
def list_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user), status: Optional[TaskStatus] = None, scope: Optional[str] = None, sort: Optional[str] = None, order: Optional[str] = None):
    q = db.query(Task).filter(Task.deleted_at.is_(None))
    if status:
        q = q.filter(Task.status == status)
    # Scope: admins can request 'all' (default); users default to 'my'
    if user.role != Role.ADMIN or scope == 'my':
        q = q.filter((Task.assignee_user_id == user.id) | (Task.created_by == user.id))
    # Sorting
    sort = (sort or 'due_at').lower()
    order = (order or 'asc').lower()
    allowed = {'due_at','updated_at','completed_at'}
    if sort not in allowed:
        sort = 'due_at'
    col = getattr(Task, sort)
    if order == 'desc':
        q = q.order_by(col.is_(None), col.desc())
    else:
        q = q.order_by(col.is_(None), col.asc())
    return q.all()

@app.get("/api/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t or t.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    if user.role != Role.ADMIN and t.assignee_user_id != user.id and t.created_by != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return t

# Viktig: bare ÉN PATCH /api/tasks/{task_id} (unngå konflikt)
@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def edit_task(task_id: int, data: TaskEdit, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")

    # Role-aware whitelist: Admin may edit all; Assignee may edit safe fields only
    payload = data.model_dump(exclude_unset=True)

    # --- NEW: Unify 'reason' -> 'body' so both Edit Reason and Reject reason share same field
    if "reason" in payload and "body" not in payload:
        payload["body"] = payload.pop("reason")

    if user.role != Role.ADMIN:
        if t.assignee_user_id != user.id and t.created_by != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        allowed = {"checklist", "address", "reason", "due_at", "title", "body"}
        disallowed = set(payload.keys()) - allowed
        if disallowed:
            raise HTTPException(status_code=403, detail=f"Fields not allowed for user: {sorted(disallowed)}")
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
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    soft_delete(db, t, user)
    return {"ok": True}

@app.post("/api/tasks/{task_id}/restore", dependencies=[Depends(require_admin)])
def restore_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    restore(db, t, user)
    return {"ok": True}

@app.post("/api/tasks/{task_id}/assign", response_model=TaskOut, dependencies=[Depends(require_admin)])
def assign_task(task_id: int, data: AssignIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
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
    evt = TaskEventType.ASSIGN if prev is None or prev == data.assignee_user_id else TaskEventType.REASSIGN
    log_event(db, t, user, evt, {"from": prev, "to": data.assignee_user_id})
    return t

@app.post("/api/tasks/{task_id}/status", response_model=TaskOut)
def change_status(task_id: int, data: StatusIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
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
        t.body = (data.reason or "").strip()  # --- NEW: persist reason into Task.body
        log_event(db, t, user, TaskEventType.REJECT, {"reason": data.reason, "at": now_iso})
    elif action == "complete":
        t.status = TaskStatus.DONE
        t.completed_at = datetime.utcnow()
        log_event(db, t, user, TaskEventType.COMPLETE, {"at": now_iso})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    db.add(t)
    db.commit()
    db.refresh(t)
    return t

# --- API route stays together and RETURNS before the fallback ---
@app.get("/api/tasks/{task_id}/events", response_model=List[TaskEventOut])
def task_events(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if user.role != Role.ADMIN and t.assignee_user_id != user.id and t.created_by != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    rows = db.execute(
        text(
            "SELECT id, task_id, type, metadata, actor_user_id, created_at "
            "FROM task_events WHERE task_id = :tid ORDER BY created_at DESC"
        ),
        {"tid": task_id}
    ).mappings().all()

    return [TaskEventOut(**dict(r)) for r in rows]


# --- keep these AT THE VERY END of main.py ---
from fastapi import Response

@app.head("/")
def head_root():
    return Response(status_code=200)

@app.get("/{full_path:path}")
def spa_fallback(full_path: str, request: Request):
    if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "assets/")):
        raise HTTPException(status_code=404)
    if os.path.isdir(static_dir):
        return FileResponse(os.path.join(static_dir, "index.html"))
    raise HTTPException(status_code=404)
