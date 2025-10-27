from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from .db import Base, engine, get_db
from .config import settings
from .models import Task, TaskStatus, TaskEventType, User, Student, Absence, Role
from .schemas import TaskIn, TaskOut, TaskEdit, AssignIn, StatusIn, TaskEventOut, AbsenceIn, AbsenceOut, StudentIn, StudentOut, HistoryItem, UserOut
from .deps import get_current_user, require_admin
from .utils import log_event, soft_delete, restore
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import Base, engine, get_db
from app.models import Task, Comment
from app.schemas import TaskUpdate, CommentCreate, CommentOut

app = FastAPI(title="Simple Task Pro API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user

@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # bare feltene som kommer inn
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(task, field, value)

    db.add(task); db.commit(); db.refresh(task)
    return {"ok": True, "id": task.id}

@app.get("/api/tasks/{task_id}/comments", response_model=list[CommentOut])
def list_comments(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    items = db.query(Comment).filter(Comment.task_id == task_id).order_by(Comment.created_at.asc()).all()
    return items

@app.post("/api/tasks/{task_id}/comments", response_model=CommentOut)
def add_comment(task_id: int, body: CommentCreate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    author = (  # les “X-User” til visningsnavn hvis du ønsker
        "Anna" if "anna" == "anna" else None
    )
    c = Comment(task_id=task_id, author=author, text=body.text.strip())
    db.add(c); db.commit(); db.refresh(c)
    return c

# Students
@app.post("/api/students", response_model=StudentOut, dependencies=[Depends(require_admin)])
def create_student(data: StudentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = Student(name=data.name, student_class=data.student_class, address=data.address)
    db.add(s); db.commit(); db.refresh(s)
    return s

@app.get("/api/students", response_model=List[StudentOut])
def list_students(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Student).all()

@app.get("/api/students/{student_id}/history", response_model=List[HistoryItem])
def student_history(student_id: int, days: int = 90, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    since = datetime.utcnow() - timedelta(days=days)
    absences = db.query(Absence).filter(Absence.student_id == student_id, Absence.date >= since.date()).all()
    items: List[HistoryItem] = []
    for a in absences:
        items.append(HistoryItem(kind="absence", date=datetime.combine(a.date, datetime.min.time()), reason_code=a.reason_code, note=a.note, reported_by=a.reported_by))
    visits = db.query(Task).filter(Task.student_id == student_id, Task.status == TaskStatus.DONE).all()
    for t in visits:
        items.append(HistoryItem(kind="visit", date=t.due_at or datetime.utcnow(), title=t.title))
    items.sort(key=lambda x: x.date, reverse=True)
    return items

# Absences
@app.post("/api/absences", response_model=AbsenceOut)
def create_absence(data: AbsenceIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = Absence(student_id=data.student_id, date=data.date, reason_code=data.reason_code, note=data.note, reported_by=data.reported_by)
    db.add(a); db.commit(); db.refresh(a)
    return a

# Tasks
@app.post("/api/tasks", response_model=TaskOut, dependencies=[Depends(require_admin)])
def create_task(data: TaskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = Task(**data.model_dump(), status=TaskStatus.NEW, created_by=user.id)
    db.add(t); db.commit(); db.refresh(t)
    log_event(db, t, user, TaskEventType.EDIT, {"create": True})
    return t

@app.get("/api/tasks", response_model=List[TaskOut])
def list_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user), status: Optional[TaskStatus] = None):
    q = db.query(Task).filter(Task.deleted_at.is_(None))
    if status:
        q = q.filter(Task.status == status)
    if user.role != Role.ADMIN:
        q = q.filter((Task.assignee_user_id == user.id) | (Task.created_by == user.id))
    return q.order_by(Task.due_at.is_(None), Task.due_at).all()

@app.get("/api/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t or t.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    if user.role != Role.ADMIN and t.assignee_user_id != user.id and t.created_by != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return t

@app.patch("/api/tasks/{task_id}", response_model=TaskOut, dependencies=[Depends(require_admin)])
def edit_task(task_id: int, data: TaskEdit, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    changed = {}
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v); changed[k] = v
    db.add(t); db.commit(); db.refresh(t)
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
    db.add(t); db.commit(); db.refresh(t)
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
    if action == "accept":
        t.status = TaskStatus.ACCEPTED
        log_event(db, t, user, TaskEventType.ACCEPT, {"at": datetime.utcnow().isoformat()})
    elif action == "reject":
        if not data.reason:
            raise HTTPException(status_code=400, detail="Reason required for reject")
        t.status = TaskStatus.REJECTED
        log_event(db, t, user, TaskEventType.REJECT, {"reason": data.reason, "at": datetime.utcnow().isoformat()})
    elif action == "complete":
        t.status = TaskStatus.DONE
        log_event(db, t, user, TaskEventType.COMPLETE, {"at": datetime.utcnow().isoformat()})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    db.add(t); db.commit(); db.refresh(t)
    return t

@app.get("/api/tasks/{task_id}/events", response_model=List[TaskEventOut])
def task_events(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if user.role != Role.ADMIN and t.assignee_user_id != user.id and t.created_by != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = db.execute(
        "SELECT id, task_id, type, metadata, actor_user_id, created_at FROM task_events WHERE task_id = :tid ORDER BY created_at DESC",
        {"tid": task_id}
    ).mappings().all()
    return [TaskEventOut(**dict(r)) for r in rows]
