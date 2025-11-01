import os
import time
import argparse
import pathlib
from datetime import datetime, date, timedelta
from typing import Tuple
from sqlalchemy.orm import Session

from app.db import Base, engine, SessionLocal
from app.models import User, Role, Student, Absence, Task, TaskStatus, TaskEventType
from app.utils import log_event

TODAY = date.today()
NOW = datetime.now().replace(minute=0, second=0, microsecond=0)

# ---------- Utility ----------

def ensure_user(db: Session, user_id: int, name: str, role: Role):
    """Opprett bruker hvis den ikke finnes, eller oppdater eksisterende."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        u = User(id=user_id, name=name, role=role)
        db.add(u)
        db.commit()
        db.refresh(u)
        print(f"[SEED] Created user {name} (id={user_id})")
    else:
        u.name = name
        u.role = role
        db.add(u)
        db.commit()
        print(f"[SEED] Updated user {name} (id={user_id})")
    return u


def _resolve_sqlite_path() -> Tuple[str, pathlib.Path]:
    db_url = str(engine.url)
    if db_url.startswith("sqlite:///"):
        db_file = db_url.replace("sqlite:///", "", 1)
        return db_url, pathlib.Path(db_file).resolve()
    if db_url.startswith("sqlite:////"):
        db_file = db_url.replace("sqlite:////", "/", 1)
        return db_url, pathlib.Path(db_file)
    return db_url, pathlib.Path("UNKNOWN")


def _log_db_target(prefix: str = "SEED"):
    db_url, db_path = _resolve_sqlite_path()
    print(f"[{prefix}] DATABASE_URL: {db_url}")
    print(f"[{prefix}] DB file     : {db_path}")


def reset_db(hard: bool = False):
    """Dropp og opprett tabeller på nytt."""
    try:
        engine.dispose()
    except Exception:
        pass

    if not hard:
        print("[RESET] soft reset: drop_all + create_all")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return

    db_url, db_path = _resolve_sqlite_path()
    print("[RESET] hard reset requested")
    if db_url.startswith("sqlite") and db_path.exists():
        try:
            os.remove(db_path)
            print(f"[RESET] removed {db_path}")
        except PermissionError:
            print("[RESET] file locked, fallback soft reset")
            Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


# ---------- Seed Data ----------

def seed():
    """Opprett demo-brukere, elever og oppgaver."""
    _log_db_target("SEED")
    with SessionLocal() as db:
        # ===== Users =====
        paddy = ensure_user(db, 1, "Paddy MacGrath", Role.ADMIN)
        ulf   = ensure_user(db, 2, "Ulf", Role.USER)
        una   = ensure_user(db, 3, "Una", Role.USER)

        # ===== Students =====
        s1 = Student(name="Oliver Smith",  student_class="10B", address="221B Baker St, London")
        s2 = Student(name="Amelia Johnson",student_class="9A",  address="10 Downing St, London")
        s3 = Student(name="Jack Williams", student_class="11C", address="Trafalgar Square, London")
        s4 = Student(name="Isla Brown",    student_class="8D",  address="1 Canada Square, London")
        s5 = Student(name="Harry Jones",   student_class="7E",  address="30 St Mary Axe, London")
        s6 = Student(name="Emily Davis",   student_class="7F",  address="Buckingham Palace, London")
        db.add_all([s1, s2, s3, s4, s5, s6])
        db.commit()

        def due(h): return datetime(TODAY.year, TODAY.month, TODAY.day, h, 0, 0)

        # ===== Tasks =====
        t1 = Task(student_id=s1.id, title="Home visit: Oliver Smith",
                  body="Verify homework plan", address=s1.address,
                  due_at=due(10), status=TaskStatus.ASSIGNED,
                  assignee_user_id=ulf.id, created_by=paddy.id)

        t2 = Task(student_id=s2.id, title="Phone call: Amelia Johnson",
                  body="Follow up on tardiness", address=s2.address,
                  due_at=due(11), status=TaskStatus.ASSIGNED,
                  assignee_user_id=ulf.id, created_by=paddy.id)

        t3 = Task(student_id=s3.id, title="Home visit: Jack Williams",
                  body="Collect consent form", address=s3.address,
                  due_at=due(12), status=TaskStatus.ASSIGNED,
                  assignee_user_id=una.id, created_by=paddy.id)

        t4 = Task(student_id=s4.id, title="Parent meeting: Isla Brown",
                  body="Behaviour plan discussion", address=s4.address,
                  due_at=due(13), status=TaskStatus.ASSIGNED,
                  assignee_user_id=una.id, created_by=paddy.id)

        db.add_all([t1, t2, t3, t4])
        db.commit()

        for t in [t1, t2, t3, t4]:
            log_event(db, t, paddy, TaskEventType.ASSIGN, {"to": t.assignee_user_id})

        total = db.query(Task).count()
        print(f"[SEED] tasks in DB after seeding: {total}")


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(description="Reset/seed test data")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--hard", action="store_true")
    args = parser.parse_args()

    if args.hard:
        reset_db(hard=True)
    elif args.reset:
        reset_db()

    seed()
    print("Seed (TEST) complete.")


if __name__ == "__main__":
    main()
