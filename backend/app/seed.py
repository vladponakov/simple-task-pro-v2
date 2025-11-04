# app/seed.py
from __future__ import annotations

import argparse
import os
import random
from datetime import date, datetime, timedelta, timezone
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.db import Base, engine, SessionLocal
from app.models import (
    User, Role, Student, Absence, Task, TaskStatus, TaskEventType
)
from app.utils import log_event

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

TODAY = date.today()
# Use timezone-aware now, then strip tzinfo so DB stays naive (matches existing schema)
NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0, tzinfo=None)

LONDON_ADDR = [
    "221B Baker St, London",
    "10 Downing St, London",
    "Trafalgar Square, London",
    "1 Canada Square, London",
    "30 St Mary Axe, London",
    "Buckingham Palace, London",
    "Tower Bridge, London",
    "King's Cross Station, London",
    "Royal Albert Hall, London",
    "Piccadilly Circus, London",
    "Covent Garden, London",
    "Canary Wharf, London",
]

FIRST = ["Oliver","Amelia","Jack","Isla","Harry","Emily","George","Sophie","Noah",
         "Ava","Leo","Mia","James","Grace","Oscar","Chloe","Thomas","Ella"]
LAST  = ["Smith","Johnson","Williams","Brown","Jones","Davis","Miller","Taylor","Wilson",
         "Moore","Clark","Hall","Young","King","Wright","Hill","Scott","Green"]


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _resolve_sqlite_path() -> Tuple[str, str]:
    """Return (db_url, resolved_file_path_or_note)."""
    db_url = str(engine.url)
    if db_url.startswith("sqlite:////"):
        return db_url, db_url.replace("sqlite:////", "/")
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "", 1)
        return db_url, os.path.abspath(path)
    return db_url, "(non-sqlite)"

def _log_db_target(prefix: str):
    db_url, db_path = _resolve_sqlite_path()
    print(f"[{prefix}] DATABASE_URL: {db_url}")
    print(f"[{prefix}] DB file     : {db_path}")

def drop_and_create():
    print("[RESET] drop_all + create_all")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def ensure_user(db: Session, user_id: int, name: str, role: Role) -> User:
    """Create or update user deterministically (SQLAlchemy 2.0 style)."""
    u = db.get(User, user_id)
    if not u:
        u = User(id=user_id, name=name, role=role)
        db.add(u); db.commit(); db.refresh(u)
        print(f"[SEED] Created user {name} (id={user_id})")
    else:
        changed = False
        if u.name != name:
            u.name = name; changed = True
        if u.role != role:
            u.role = role; changed = True
        if changed:
            db.add(u); db.commit()
            print(f"[SEED] Updated user {name} (id={user_id})")
    return u

def _mk_name() -> str:
    return f"{random.choice(FIRST)} {random.choice(LAST)}"

def _mk_addr() -> str:
    return random.choice(LONDON_ADDR)

def _due(hour: int) -> datetime:
    # today at given hour (naive datetime)
    return datetime(TODAY.year, TODAY.month, TODAY.day, hour, 0, 0)


# ---------------------------------------------------------------------
# Seed payload builders
# ---------------------------------------------------------------------

def seed_minimal(db: Session, paddy: User, ulf: User, una: User):
    """Small, complete dataset for quick demo."""
    s1 = Student(name="Oliver Smith",  student_class="10B", address=LONDON_ADDR[0])
    s2 = Student(name="Amelia Johnson",student_class="9A",  address=LONDON_ADDR[1])
    s3 = Student(name="Jack Williams", student_class="11C", address=LONDON_ADDR[2])
    s4 = Student(name="Isla Brown",    student_class="8D",  address=LONDON_ADDR[3])
    db.add_all([s1, s2, s3, s4]); db.commit()

    for s in [s1, s2, s3, s4]:
        db.add(Absence(
            student_id=s.id,
            date=TODAY - timedelta(days=random.randint(1, 7)),
            reason_code="Syk",
            note="Flu",
            reported_by="Teacher"
        ))
    db.commit()

    t1 = Task(
        student_id=s1.id,
        title="Home visit: Oliver Smith",
        body="Check plan",
        address=s1.address,
        checklist=[{"text": "Knock door", "done": False}],
        due_at=_due(10),
        status=TaskStatus.ASSIGNED,
        assignee_user_id=ulf.id,
        created_by=paddy.id,
    )
    t2 = Task(
        student_id=s2.id,
        title="Phone call: Amelia Johnson",
        body="Follow up",
        address=s2.address,
        checklist=[{"text": "Call guardian", "done": False}],
        due_at=_due(11),
        status=TaskStatus.ASSIGNED,
        assignee_user_id=ulf.id,
        created_by=paddy.id,
    )
    t3 = Task(
        student_id=s3.id,
        title="Home visit: Jack Williams",
        body="Collect form",
        address=s3.address,
        checklist=[{"text": "Bring pack", "done": False}],
        due_at=_due(12),
        status=TaskStatus.ASSIGNED,
        assignee_user_id=una.id,
        created_by=paddy.id,
    )
    t4 = Task(
        student_id=s4.id,
        title="Parent meeting: Isla Brown",
        body="Behaviour plan",
        address=s4.address,
        checklist=[],
        due_at=_due(13),
        status=TaskStatus.NEW,
        assignee_user_id=None,
        created_by=paddy.id,
    )
    db.add_all([t1, t2, t3, t4]); db.commit()

    for t in [t1, t2, t3]:
        log_event(db, t, paddy, TaskEventType.ASSIGN, {"to": t.assignee_user_id})

    print(f"[SEED] Minimal: tasks={db.query(Task).count()}, students={db.query(Student).count()}")


def seed_big(db: Session, paddy: User, ulf: User, una: User, students: int = 60):
    """Large demo: many students (London), tasks spread across Ulf/Una + some NEW."""
    studs: List[Student] = []
    for _ in range(students):
        s = Student(name=_mk_name(), student_class=str(7 + random.randint(0, 5)) + "A", address=_mk_addr())
        studs.append(s)
    db.add_all(studs); db.commit()

    # Absence history (1–3 per student)
    for s in studs:
        for _ in range(random.randint(1, 3)):
            db.add(Absence(
                student_id=s.id,
                date=TODAY - timedelta(days=random.randint(1, 14)),
                reason_code=random.choice(["Syk", "Reise", "Annet"]),
                note="Auto-generated",
                reported_by=random.choice(["Teacher", "Admin"]),
            ))
    db.commit()

    # Tasks: 1 per student
    tasks = []
    for i, s in enumerate(studs):
        assignee = ulf if i % 2 == 0 else una
        status = random.choice([TaskStatus.ASSIGNED, TaskStatus.ACCEPTED, TaskStatus.NEW])
        t = Task(
            student_id=s.id,
            title=f"Visit: {s.name}",
            body="Auto generated check",
            address=s.address,
            checklist=[{"text": "Knock door", "done": False}, {"text": "Add note", "done": False}],
            due_at=_due(9 + (i % 6)),
            status=status,
            assignee_user_id=None if status == TaskStatus.NEW else assignee.id,
            created_by=paddy.id,
        )
        tasks.append(t)
    db.add_all(tasks); db.commit()

    for t in tasks:
        if t.assignee_user_id:
            log_event(db, t, paddy, TaskEventType.ASSIGN, {"to": t.assignee_user_id})

    print(f"[SEED] Big: students={len(studs)}, tasks={len(tasks)}")


# ---------------------------------------------------------------------
# Flows
# ---------------------------------------------------------------------

def do_reset_and_seed(big: int | None):
    _log_db_target("SEED")
    drop_and_create()
    with SessionLocal() as db:
        paddy = ensure_user(db, 1, "Paddy MacGrath", Role.ADMIN)
        ulf   = ensure_user(db, 2, "Ulf", Role.USER)
        una   = ensure_user(db, 3, "Una", Role.USER)

        if big and big > 0:
            seed_big(db, paddy, ulf, una, students=big)
        else:
            seed_minimal(db, paddy, ulf, una)

def do_ensure(big: int | None):
    """Idempotent: creates users and minimal data if DB is empty.
       If --big N is passed, adds large demo set even if data exists."""
    _log_db_target("ENSURE")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        paddy = ensure_user(db, 1, "Paddy MacGrath", Role.ADMIN)
        ulf   = ensure_user(db, 2, "Ulf", Role.USER)
        una   = ensure_user(db, 3, "Una", Role.USER)

        have_tasks = db.query(Task).count()
        have_students = db.query(Student).count()

        if big and big > 0:
            print("[ENSURE] big mode → adding data regardless of existing rows")
            seed_big(db, paddy, ulf, una, students=big)
            return

        if have_tasks == 0 and have_students == 0:
            print("[ENSURE] empty DB → creating minimal demo set")
            seed_minimal(db, paddy, ulf, una)
        else:
            print(f"[ENSURE] leaving existing data (students={have_students}, tasks={have_tasks})")


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed/Ensure demo data for Simple Task Pro.")
    parser.add_argument("--reset", action="store_true",
                        help="Drop & recreate tables, then seed.")
    parser.add_argument("--ensure", action="store_true",
                        help="Idempotent: create if empty; never delete.")
    parser.add_argument("--big", type=int, default=0,
                        help="Also add a large demo set (N students, e.g. 60).")
    args = parser.parse_args()

    if args.reset and args.ensure:
        print("[WARN] both --reset and --ensure → using --reset")
        args.ensure = False

    if args.reset:
        do_reset_and_seed(args.big)
    elif args.ensure or args.big > 0:
        do_ensure(args.big)
    else:
        # default to ensure minimal
        do_ensure(0)

    print("Seed complete.")

if __name__ == "__main__":
    main()
