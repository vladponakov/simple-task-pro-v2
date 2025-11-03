from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.config import settings
from app.models import (
    Task, TaskStatus, TaskEventType, User, Student, Absence, Role, Comment
)
from app.schemas import (
    UserOut, TaskIn, TaskOut, TaskEdit, AssignIn, StatusIn, TaskEventOut,
    AbsenceIn, AbsenceOut, StudentIn, StudentOut, HistoryItem,
    CommentCreate, CommentOut
)
from app.deps import get_current_user, require_admin
from app.utils import log_event, soft_delete, restore

# -------------------- App + CORS --------------------

# CORS_ORIGINS may be a list or a comma-separated string in settings
if isinstance(settings.CORS_ORIGINS, str):
    _origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
else:
    _origins = settings.CORS_ORIGINS

app = FastAPI(title="Simple Task Pro API v2")

app.add_middleware(
    CORSMiddleware,
    # Same-origin in production (no CORS). Allow localhost for dev:
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# where the built frontend is copied by Render's build step
static_dir = os.path.join(os.path.dirname(__file__), "static")

# Serve hashed assets like /assets/index-XXXX.js and .css
assets_dir = os.path.join(static_dir, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Avoid caching index.html so the latest UI is loaded after deploys
@app.middleware("http")
async def no_cache_index(request: Request, call_next):
    resp: Response = await call_next(request)
    if request.url.path in ("/", "/index.html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

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

# -------------------- Students --------------------

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

# -------------------- Absences --------------------

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

# -------------------- Tasks --------------------

@app.post("/api/tasks", response_model=TaskOut, dependencies=[Depends(require_admin)])
def create_task(data: TaskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = Task(**data.model_dump(), status=TaskStatus.NEW, created_by=user.id)
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
    order: Optional[str] = None
):
    q = db.query(Task).filter(Task.deleted_at.is_(None))
    if status:
        q = q.filter(Task.status == status)
    # Scope: admins can request 'all' (default); users default to 'my'
    if user.role != Role.ADMIN or scope == 'my':
        q = q.filter((Task.assignee_user_id == user.id) | (Task.created_by == user.id))
    # Sorting
    sort = (sort or 'due_at').lower()
    order = (order or 'asc').lower()
    allowed = {'due_at', 'updated_at', 'completed_at'}
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

# Single edit endpoint for tasks
@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def edit_task(task_id: int, data: TaskEdit, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")

    payload = data.model_dump(exclude_unset=True)

    # Unify "reason" -> "body" so Edit Reason and Reject Reason share the same field
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
        t.body = (data.reason or "").strip()  # store reason in Task.body
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

# -------------------- SPA fallback (last) --------------------

@app.head("/")
def head_root():
    return Response(status_code=200)

@app.get("/{full_path:path}")
def spa_fallback(full_path: str, request: Request):
    # Let mounted routes (/assets, /api, docs) take priority; this is last resort.
    if os.path.isdir(static_dir):
        return FileResponse(os.path.join(static_dir, "index.html"))
    raise HTTPException(status_code=404)
