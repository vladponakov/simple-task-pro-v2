# app/seed.py
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from random import choice, randint
from typing import Optional, List

from app.db import Base, engine, SessionLocal
from app.models import User, Student, Task, Role  # Role is an Enum; DB stores strings

UTC = timezone.utc
NOW = datetime.now(UTC)

# ---------------- helpers ----------------

def _as_str_role(role_or_str) -> str:
    """Normalize enum/string to plain string for storage/prints."""
    return getattr(role_or_str, "value", role_or_str)

def ensure_user(s, id_: int, name: str, role: Role) -> User:
    u: Optional[User] = s.get(User, id_)
    role_str = _as_str_role(role)
    if not u:
        u = User(id=id_, name=name, role=role_str)
        s.add(u); s.commit(); s.refresh(u)
        print(f"[SEED] created user #{id_}: {name} ({role_str})")
    else:
        changed = False
        if u.name != name:
            u.name = name; changed = True
        if u.role != role_str:
            u.role = role_str; changed = True
        if changed:
            s.add(u); s.commit(); s.refresh(u)
            print(f"[SEED] updated user #{id_}: {name} ({role_str})")
    return u

def ensure_student(s, name: str, address: str) -> Student:
    """Create student if missing. Only sets optional attrs if the model has them."""
    st = s.query(Student).filter_by(name=name).first()
    if not st:
        st = Student(name=name)
        if hasattr(st, "student_class"):
            setattr(st, "student_class", "10A")
        if hasattr(st, "address"):
            setattr(st, "address", address)
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

def _student_address_or_fallback(st: Student) -> str:
    """Use Student.address if present; otherwise fall back to a random London address."""
    if hasattr(st, "address") and getattr(st, "address", None):
        return getattr(st, "address")
    return choice(LONDON_ADDRS)

def mk_task(st: Student, assignee_id: Optional[int], status_str: str) -> Task:
    t = Task(
        student_id=st.id,
        title=f"Visit: {st.name}",
        address=_student_address_or_fallback(st),
        body="Auto-generated task",
        due_at=due_in(randint(2, 72)),
        assignee_user_id=assignee_id,
        status=status_str,  # plain string: "New" | "Assigned" | "Done"
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
        Task(student_id=s1.id, title="Home visit: Oliver Smith",
             address=_student_address_or_fallback(s1),
             body="Check plan", checklist=[{"text":"Knock door","done":False}],
             due_at=due_in(6), status="Assigned", assignee_user_id=ulf.id, created_by=admin.id),

        Task(student_id=s2.id, title="Phone call: Amelia Johnson",
             address=_student_address_or_fallback(s2),
             body="Follow up", checklist=[{"text":"Call guardian","done":False}],
             due_at=due_in(8), status="Assigned", assignee_user_id=ulf.id, created_by=admin.id),

        Task(student_id=s3.id, title="Home visit: Jack Williams",
             address=_student_address_or_fallback(s3),
             body="Collect form", checklist=[{"text":"Bring pack","done":False}],
             due_at=due_in(10), status="Assigned", assignee_user_id=una.id, created_by=admin.id),

        Task(student_id=s4.id, title="Parent meeting: Isla Brown",
             address=_student_address_or_fallback(s4),
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
