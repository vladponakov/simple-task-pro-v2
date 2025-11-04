# ================================================================
# BLOCK: SEED
# Purpose: Idempotent seeding for Simple Task Pro (no CSV needed)
# Models expected: User, Student, Task, TaskComment, StudentHistory
# Status values: "New" | "Assigned" | "Rejected" | "Done"
# ================================================================

from __future__ import annotations
import argparse
import os
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .db import Base, engine, SessionLocal
from .models import User, Student, Task, TaskComment, StudentHistory

UTC = timezone.utc

# ------------------------ helpers ------------------------

def now_utc():
    return datetime.now(tz=UTC).replace(microsecond=0)

def today_at(hour: int, minute: int = 0):
    t = datetime.now(tz=UTC).astimezone(UTC)
    return t.replace(hour=hour, minute=minute, second=0, microsecond=0)

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

FIRST = ["Oliver","Amelia","Jack","Isla","Harry","Emily","George","Sophie","Noah","Ava","Leo","Mia","James","Grace","Oscar","Chloe","Thomas","Ella"]
LAST  = ["Smith","Johnson","Williams","Brown","Jones","Davis","Miller","Taylor","Wilson","Moore","Clark","Hall","Young","King","Wright","Hill","Scott","Green"]

def mk_name():
    return f"{random.choice(FIRST)} {random.choice(LAST)}"

def mk_addr():
    return random.choice(LONDON_ADDR)

# ------------------------ ensure primitives ------------------------

def ensure_user(db: Session, user_id: int, name: str, role: str) -> User:
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        u = User(id=user_id, name=name, role=role)
        db.add(u); db.commit(); db.refresh(u)
        print(f"[SEED] created user #{user_id}: {name} ({role})")
    else:
        changed = False
        if u.name != name:
            u.name = name; changed = True
        if u.role != role:
            u.role = role; changed = True
        if changed:
            db.add(u); db.commit()
            print(f"[SEED] updated user #{user_id}: {name} ({role})")
    return u

def ensure_students(db: Session, names_with_addrs: list[tuple[str,str]]) -> list[Student]:
    out = []
    for nm, addr in names_with_addrs:
        s = db.query(Student).filter(Student.name == nm).first()
        if not s:
            s = Student(name=nm)
            db.add(s); db.commit(); db.refresh(s)
            out.append(s)
        else:
            out.append(s)
    return out

# ------------------------ seed datasets ------------------------

def seed_minimal(db: Session, admin: User, u1: User, u2: User):
    """Small, clean demo: 4 students, 4 tasks (2→Ulf, 1→Una, 1 New)."""
    s_names = [
        ("Oliver Smith", LONDON_ADDR[0]),
        ("Amelia Johnson", LONDON_ADDR[1]),
        ("Jack Williams", LONDON_ADDR[2]),
        ("Isla Brown", LONDON_ADDR[3]),
    ]
    studs = ensure_students(db, s_names)

    # tasks
    t1 = Task(
        student_id=studs[0].id,
        title="Home visit: Oliver Smith",
        body="Check action plan",
        address=s_names[0][1],
        checklist=[{"text": "Knock door", "done": False}],
        due_at=today_at(9),
        assignee_user_id=u1.id,
        status="Assigned",
        created_by=admin.id,
    )
    t2 = Task(
        student_id=studs[1].id,
        title="Phone call: Amelia Johnson",
        body="Follow up attendance",
        address=s_names[1][1],
        checklist=[{"text": "Call guardian", "done": False}],
        due_at=today_at(10),
        assignee_user_id=u1.id,
        status="Assigned",
        created_by=admin.id,
    )
    t3 = Task(
        student_id=studs[2].id,
        title="Home visit: Jack Williams",
        body="Collect signed form",
        address=s_names[2][1],
        checklist=[{"text": "Bring pack", "done": False}],
        due_at=today_at(11),
        assignee_user_id=u2.id,
        status="Assigned",
        created_by=admin.id,
    )
    t4 = Task(
        student_id=studs[3].id,
        title="Parent meeting: Isla Brown",
        body="Behavior plan intro",
        address=s_names[3][1],
        checklist=[],
        due_at=today_at(12),
        assignee_user_id=None,
        status="New",
        created_by=admin.id,
    )
    db.add_all([t1, t2, t3, t4]); db.commit()

    # minimal history & comments
    for s in studs:
        db.add(StudentHistory(student_id=s.id, type="absence", note="Auto sample", created_at=now_utc() - timedelta(days=random.randint(1,7))))
    db.commit()

    db.add(TaskComment(task_id=t1.id, author="Paddy", text="Remember photo ID"))
    db.add(TaskComment(task_id=t2.id, author="Ulf", text="Called parent, no answer"))
    db.commit()

    print(f"[SEED] minimal: students={len(studs)}, tasks=4")

def seed_big(db: Session, admin: User, u1: User, u2: User, students: int = 40):
    studs: list[Student] = []
    for _ in range(students):
        s = Student(name=mk_name())
        db.add(s); studs.append(s)
    db.commit()

    for s in studs:
        for _ in range(random.randint(1, 3)):
            db.add(StudentHistory(student_id=s.id, type=random.choice(["absence","visit"]), note="Auto", created_at=now_utc() - timedelta(days=random.randint(1,14))))
    db.commit()

    tasks = []
    for i, s in enumerate(studs):
        assignee = u1 if i % 2 == 0 else u2
        status = random.choice(["Assigned", "New", "Assigned", "Assigned"])
        due = today_at(9 + (i % 6))
        t = Task(
            student_id=s.id,
            title=f"Visit: {s.name}",
            body="Auto generated check",
            address=mk_addr(),
            checklist=[{"text":"Knock door","done":False},{"text":"Add note","done":False}],
            due_at=due,
            assignee_user_id=None if status == "New" else assignee.id,
            status=status,
            created_by=admin.id,
        )
        tasks.append(t)
    db.add_all(tasks); db.commit()
    print(f"[SEED] big: students={len(studs)}, tasks={len(tasks)}")

# ------------------------ flows ------------------------

def do_reset_and_seed(big: int | None):
    print("[SEED] reset → drop_all + create_all")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin = ensure_user(db, 1, "Paddy MacGrath", "Admin")
        u1    = ensure_user(db, 2, "Ulf", "User")
        u2    = ensure_user(db, 3, "Una", "User")
        if big and big > 0:
            seed_big(db, admin, u1, u2, students=big)
        else:
            seed_minimal(db, admin, u1, u2)
    print("[SEED] reset done.")

def do_ensure(big: int | None):
    print("[SEED] ensure → create tables if missing; seed if empty")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin = ensure_user(db, 1, "Paddy MacGrath", "Admin")
        u1    = ensure_user(db, 2, "Ulf", "User")
        u2    = ensure_user(db, 3, "Una", "User")

        have_tasks = db.query(Task).count()
        have_students = db.query(Student).count()
        if big and big > 0:
            print("[SEED] big requested → adding data regardless of existing rows")
            seed_big(db, admin, u1, u2, students=big)
            return

        if have_tasks == 0 and have_students == 0:
            print("[SEED] empty DB → seed minimal")
            seed_minimal(db, admin, u1, u2)
        else:
            print(f"[SEED] keeping existing data (students={have_students}, tasks={have_tasks})")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true", help="Drop & recreate tables, then seed")
    p.add_argument("--ensure", action="store_true", help="Create tables and minimal data if DB is empty")
    p.add_argument("--big", type=int, default=0, help="Seed a larger dataset (N students)")
    args = p.parse_args()

    if args.reset and args.ensure:
        print("[SEED] both --reset and --ensure given → using --reset")
        args.ensure = False

    if args.reset:
        do_reset_and_seed(args.big)
    elif args.ensure or args.big > 0:
        do_ensure(args.big)
    else:
        do_ensure(0)

    print("[SEED] complete.")

if __name__ == "__main__":
    main()
