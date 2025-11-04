# app/seed.py
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from random import choice, randint
from typing import Optional, List

from app.db import Base, engine, SessionLocal
from app.models import User, Student, Task, Role  # NOTE: no TaskStatus import

UTC = timezone.utc
NOW = datetime.now(UTC)

# ---------------- helpers ----------------

def ensure_user(s, id_: int, name: str, role: Role) -> User:
    u: Optional[User] = s.get(User, id_)
    if not u:
        u = User(id=id_, name=name, role=role)
        s.add(u); s.commit(); s.refresh(u)
        print(f"[SEED] created user #{id_}: {name} ({role.value})")
    else:
        changed = False
        if u.name != name: u.name, changed = name, True
        if u.role != role: u.role, changed = role, True
        if changed:
            s.add(u); s.commit(); s.refresh(u)
            print(f"[SEED] updated user #{id_}: {name} ({role.value})")
    return u

def ensure_student(s, name: str, address: str) -> Student:
    st = s.query(Student).filter_by(name=name).first()
    if not st:
        st = Student(name=name, student_class="10A", address=address)
        s.add(st); s.commit(); s.refresh(st)
    return st

LONDON_ADDRS = [
    "221B Baker St, London","10 Downing St, London","Trafalgar Square, London",
    "1 Canada Square, London","30 St Mary Axe, London","Buckingham Palace, London",
    "Tower Bridge, London","King's Cross Station, London","Royal Albert Hall, London",
    "Abbey Road, London",
]

NAMES = [
    "Oliver Smith","Amelia Johnson","Jack Williams","Isla Brown","Harry Jones",
    "Emily Davis","George Miller","Sophie Taylor","Noah Wilson","Mia Moore",
    "Thomas Anderson","Ava Thompson","Leo White","Grace Harris","Oscar Martin",
    "Ella Clark","Lucas Lewis","Lily Walker","James Hall","Freya Allen",
    "Daniel Young","Ruby King","Max Scott","Ivy Green","Aaron Baker",
    "Nora Adams","Theo Turner","Chloe Parker","Hugo Evans","Emma Collins",
]

def due_in(hours: int):
    return NOW + timedelta(hours=hours)

def mk_task(st: Student, assignee_id: Optional[int], status_str: str) -> Task:
    t = Task(
        student_id=st.id,
        title=f"Visit: {st.name}",
        address=st.address,
        body="Auto-generated task",
        due_at=due_in(randint(2, 72)),
        assignee_user_id=assignee_id,
        status=status_str,  # plain string
        checklist=[{"text":"Knock door","done":False},{"text":"Add note","done":False}],
        external_ref=None,
        created_by=1,
    )
    if status_str == "Done":
        t.completed_at = NOW
    return t

# --------------- seeds -------------------

def seed_minimal(s, admin: User, ulf: User, una: User):
    s1 = ensure_student(s, "Oliver Smith",  LONDON_ADDRS[0])
    s2 = ensure_student(s, "Amelia Johnson",LONDON_ADDRS[1])
    s3 = ensure_student(s, "Jack Williams", LONDON_ADDRS[2])
    s4 = ensure_student(s, "Isla Brown",    LONDON_ADDRS[3])

    tasks = [
        Task(student_id=s1.id, title="Home visit: Oliver Smith", address=s1.address,
             body="Check plan", checklist=[{"text":"Knock door","done":False}],
             due_at=due_in(6), status="Assigned", assignee_user_id=ulf.id, created_by=admin.id),
        Task(student_id=s2.id, title="Phone call: Amelia Johnson", address=s2.address,
             body="Follow up", checklist=[{"text":"Call guardian","done":False}],
             due_at=due_in(8), status="Assigned", assignee_user_id=ulf.id, created_by=admin.id),
        Task(student_id=s3.id, title="Home visit: Jack Williams", address=s3.address,
             body="Collect form", checklist=[{"text":"Bring pack","done":False}],
             due_at=due_in(10), status="Assigned", assignee_user_id=una.id, created_by=admin.id),
        Task(student_id=s4.id, title="Parent meeting: Isla Brown", address=s4.address,
             body="Behaviour plan", checklist=[],
             due_at=due_in(12), status="New", assignee_user_id=None, created_by=admin.id),
    ]
    s.add_all(tasks); s.commit()
    print(f"[SEED] minimal: students=4, tasks=4")

def seed_big(s, admin: User, ulf: User, una: User, students: int = 60, tasks_per_student: int = 2):
    pool = (NAMES * ((students // len(NAMES)) + 1))[:students]
    studs: List[Student] = [ensure_student(s, nm, choice(LONDON_ADDRS)) for nm in pool]

    created = 0
    assignees = [ulf.id, una.id]
    for st in studs:
        existing = s.query(Task).filter(Task.student_id == st.id, Task.deleted_at.is_(None)).count()
        to_make = max(0, tasks_per_student - existing)
        for _ in range(to_make):
            status_str = choice(["New", "Assigned", "Done", "Assigned"])
            assignee = choice(assignees) if status_str in ("Assigned", "Done") else None
            s.add(mk_task(st, assignee, status_str)); created += 1
    if created:
        s.commit()
    print(f"[SEED] big: students={len(studs)}, added_tasks=+{created}")

# --------------- flows -------------------

def do_reset_and_seed(big: int):
    print("[SEED] reset → drop_all + create_all")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as s:
        admin = ensure_user(s, 1, "Paddy MacGrath", Role.ADMIN)
        ulf   = ensure_user(s, 2, "Ulf", Role.USER)
        una   = ensure_user(s, 3, "Una", Role.USER)
        if big > 0:
            seed_big(s, admin, ulf, una, students=big)
        else:
            seed_minimal(s, admin, ulf, una)
    print("[SEED] reset done.")

def do_ensure(big: int):
    print("[SEED] ensure → create tables if missing; seed if empty")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as s:
        admin = ensure_user(s, 1, "Paddy MacGrath", Role.ADMIN)
        ulf   = ensure_user(s, 2, "Ulf", Role.USER)
        una   = ensure_user(s, 3, "Una", Role.USER)

        have_students = s.query(Student).count()
        have_tasks    = s.query(Task).count()

        if big > 0:
            seed_big(s, admin, ulf, una, students=big)
        elif have_students == 0 and have_tasks == 0:
            seed_minimal(s, admin, ulf, una)
        else:
            print(f"[SEED] DB already has data (students={have_students}, tasks={have_tasks}) → leaving as-is")

def main():
    import sys
    p = argparse.ArgumentParser()
    p.add_argument("--reset",  action="store_true", help="Drop & recreate tables, then seed")
    p.add_argument("--ensure", action="store_true", help="Idempotent: create if empty; never delete")
    p.add_argument("--big",    type=int, default=0,   help="Seed larger demo (N students, e.g. 60)")
    args = p.parse_args()

    # if flag --big given without value, default to 60
    big = args.big if args.big > 0 else (60 if "--big" in sys.argv else 0)

    if args.reset and args.ensure:
        print("[WARN] both --reset and --ensure passed → using --reset")
        args.ensure = False

    if args.reset:
        do_reset_and_seed(big)
    elif args.ensure:
        do_ensure(big)
    else:
        do_ensure(0)

    print("[SEED] complete.")

if __name__ == "__main__":
    main()
