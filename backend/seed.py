import os
import time
import argparse
import pathlib
from datetime import datetime, date, timedelta
from typing import Tuple

from sqlalchemy.orm import Session

# --- Prosjekt-importer: disse forutsetter din mappestruktur ---
from app.db import Base, engine, SessionLocal  # samme kilde som appen bruker
from app.models import (
    User, Role, Student, Absence, Task, TaskStatus, TaskEventType
)
from app.utils import log_event


TODAY = date.today()
NOW = datetime.now().replace(minute=0, second=0, microsecond=0)


# --------- Hjelpere ---------
def _resolve_sqlite_path() -> Tuple[str, pathlib.Path]:
    """
    Finn (absolutt) sti til SQLite-filen appen/engine faktisk bruker.
    Fungerer både for sqlite:///relative.db og sqlite:////absolute.db.
    """
    db_url = str(engine.url)
    if db_url.startswith("sqlite:///"):
        db_file = db_url.replace("sqlite:///", "", 1)
        return db_url, pathlib.Path(db_file).resolve()
    if db_url.startswith("sqlite:////"):
        # allerede absolutt
        db_file = db_url.replace("sqlite:////", "/", 1)
        return db_url, pathlib.Path(db_file)
    # Andre drivere (Postgres etc.)
    return db_url, pathlib.Path("UNKNOWN (non-sqlite)")


def _log_db_target(prefix: str = "SEED"):
    db_url, db_path = _resolve_sqlite_path()
    print(f"[{prefix}] DATABASE_URL: {db_url}")
    print(f"[{prefix}] DB file     : {db_path}")


# --------- Reset-funksjoner ---------
def reset_db(hard: bool = False):
    """
    Robust reset av skjema uten å være avhengig av å slette selve SQLite-filen.
    - soft (default):   drop_all + create_all (behagelig i Windows; unngår låser)
    - hard (--hard):    forsøk å slette app.db med retry; om lås -> fall tilbake til soft
    """
    # sørg for at alle pool-conn lukkes før vi manipulerer
    try:
        engine.dispose()
    except Exception:
        pass

    if not hard:
        print("[RESET] soft reset: drop_all + create_all")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return

    # hard reset: prøv å slette filen hvis det er sqlite
    db_url, db_path = _resolve_sqlite_path()
    print("[RESET] hard reset requested")
    if db_url.startswith("sqlite"):
        if db_path.exists():
            print(f"[RESET] trying to remove {db_path}")
            removed = False
            for _ in range(8):  # ~4 sekunder retry
                try:
                    os.remove(db_path)
                    removed = True
                    print("[RESET] file removed")
                    break
                except PermissionError:
                    time.sleep(0.5)

            if not removed:
                print("[RESET] still locked; falling back to soft reset")
                Base.metadata.drop_all(bind=engine)
                Base.metadata.create_all(bind=engine)
                return

            # ny tom fil via create_all
            Base.metadata.create_all(bind=engine)
        else:
            print("[RESET] file not found; create_all()")
            Base.metadata.create_all(bind=engine)
    else:
        # ikke-sqlite (Postgres, etc.) → standard soft
        print("[RESET] non-sqlite; performing soft reset")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)


# --------- Seed-data ---------
def seed():
    """
    Fyller databasen med testbrukere, elever, fravær, tasks og hendelser.
    """
    _log_db_target("SEED")
    with SessionLocal() as db:  # auto-close, rollback on exception
        # ===== Users =====
        paddy = User(name="Paddy MacGrath Admin", role=Role.ADMIN)   # Admin
        ulf  = User(name="Ulf",        role=Role.USER)    # User 1
        una  = User(name="Una",        role=Role.USER)    # User 2
        liam = User(name="Liam",       role=Role.USER)    # User 3
        db.add_all([paddy, ulf, una, liam]); db.commit()
        db.refresh(paddy); db.refresh(ulf); db.refresh(una); db.refresh(liam)

        # ===== Students (London addresses) =====
        s1 = Student(name="Oliver Smith",  student_class="10B", address="221B Baker St, London")
        s2 = Student(name="Amelia Johnson",student_class="9A",  address="10 Downing St, London")
        s3 = Student(name="Jack Williams", student_class="11C", address="Trafalgar Square, London")
        s4 = Student(name="Isla Brown",    student_class="8D",  address="1 Canada Square, London")
        s5 = Student(name="Harry Jones",   student_class="7E",  address="30 St Mary Axe, London")
        s6 = Student(name="Emily Davis",   student_class="7F",  address="Buckingham Palace, London")
        s7 = Student(name="George Miller", student_class="6A",  address="Tower Bridge, London")
        s8 = Student(name="Sophie Taylor", student_class="9C",  address="King's Cross Station, London")
        s9 = Student(name="Noah Wilson",   student_class="8B",  address="Royal Albert Hall, London")
        db.add_all([s1,s2,s3,s4,s5,s6,s7,s8,s9]); db.commit()

        # ===== Absence history =====
        db.add_all([
            Absence(student_id=s1.id, date=TODAY - timedelta(days=2),  reason_code="Syk",   note="Fever",        reported_by="Teacher"),
            Absence(student_id=s1.id, date=TODAY - timedelta(days=1),  reason_code="Syk",   note="Recovering",   reported_by="Teacher"),
            Absence(student_id=s2.id, date=TODAY - timedelta(days=3),  reason_code="Reise", note="Family visit", reported_by="Admin"),
            Absence(student_id=s3.id, date=TODAY - timedelta(days=9),  reason_code="Annet", note="Doctor visit", reported_by="Teacher"),
            Absence(student_id=s4.id, date=TODAY - timedelta(days=7),  reason_code="Syk",   note="Cold",         reported_by="Teacher"),
            Absence(student_id=s5.id, date=TODAY - timedelta(days=6),  reason_code="Reise", note="Competition",  reported_by="Admin"),
            Absence(student_id=s6.id, date=TODAY,                      reason_code="Syk",   note="Headache",     reported_by="Teacher"),
            Absence(student_id=s7.id, date=TODAY - timedelta(days=4),  reason_code="Annet", note="Moving",       reported_by="Admin"),
            Absence(student_id=s8.id, date=TODAY - timedelta(days=1),  reason_code="Syk",   note="Flu suspicion",reported_by="Teacher"),
            Absence(student_id=s9.id, date=TODAY - timedelta(days=12), reason_code="Annet", note="Dentist",      reported_by="Teacher"),
        ])
        db.commit()

        def due(hh): return datetime(TODAY.year, TODAY.month, TODAY.day, hh, 0, 0)

        # --- User 1 (Ulf)
        t1 = Task(student_id=s1.id, title="Home visit: Oliver Smith",
                  body="Verify homework plan; discuss recent absence.",
                  address=s1.address, checklist=[{"text":"Knock the door","done":False},{"text":"Check absence notes","done":False}],
                  due_at=due(10), status=TaskStatus.ASSIGNED, assignee_user_id=ulf.id, created_by=paddy.id)

        t2 = Task(student_id=s2.id, title="Phone call: Amelia Johnson",
                  body="Follow up on tardiness.", address=s2.address,
                  checklist=[{"text":"Call guardian","done":False}], due_at=due(11),
                  status=TaskStatus.ASSIGNED, assignee_user_id=ulf.id, created_by=paddy.id)

        t3_done = Task(student_id=s1.id, title="Earlier visit: Oliver Smith",
                  body="Weekly check", address=s1.address, checklist=[],
                  due_at=NOW - timedelta(days=2), status=TaskStatus.DONE, assignee_user_id=ulf.id, created_by=paddy.id)

        t_rej = Task(student_id=s8.id, title="Welfare check: Sophie Taylor",
                  body="Confirm attendance tomorrow.", address=s8.address, checklist=[],
                  due_at=due(14), status=TaskStatus.REJECTED, assignee_user_id=ulf.id, created_by=paddy.id)

        # --- User 2 (Una)
        t4 = Task(student_id=s3.id, title="Home visit: Jack Williams",
                  body="Collect consent form.", address=s3.address,
                  checklist=[{"text":"Bring consent pack","done":False}], due_at=due(10),
                  status=TaskStatus.ASSIGNED, assignee_user_id=una.id, created_by=paddy.id)

        t5 = Task(student_id=s4.id, title="Parent meeting: Isla Brown",
                  body="Behaviour plan discussion.", address=s4.address,
                  checklist=[], due_at=due(12), status=TaskStatus.ASSIGNED, assignee_user_id=una.id, created_by=paddy.id)

        t6 = Task(student_id=s5.id, title="Welfare check: Harry Jones",
                  body="Follow up after absence.", address=s5.address,
                  checklist=[], due_at=due(13), status=TaskStatus.ASSIGNED, assignee_user_id=una.id, created_by=paddy.id)

        # --- New queue items (unassigned)
        t_new1 = Task(student_id=s6.id, title="New: Emily Davis",
                  body="Create visit plan.", address=s6.address, checklist=[{"text":"Draft plan","done":False}],
                  due_at=due(15), status=TaskStatus.NEW, assignee_user_id=None, created_by=paddy.id)

        t_new2 = Task(student_id=s7.id, title="New: George Miller",
                  body="Initial contact.", address=s7.address, checklist=[],
                  due_at=due(16), status=TaskStatus.NEW, assignee_user_id=None, created_by=paddy.id)

        # --- Accepted example
        t_acc = Task(student_id=s9.id, title="Check-in: Noah Wilson",
                  body="Short progress check.", address=s9.address, checklist=[],
                  due_at=due(9), status=TaskStatus.ACCEPTED, assignee_user_id=una.id, created_by=paddy.id)

        db.add_all([t1,t2,t3_done,t_rej,t4,t5,t6,t_new1,t_new2,t_acc]); db.commit()

        # ===== Audit trail =====
        for t in [t1,t2,t4,t5,t6,t_acc]:
            log_event(db, t, paddy, TaskEventType.ASSIGN, {"to": t.assignee_user_id})
        log_event(db, t3_done, ulf, TaskEventType.COMPLETE, {"at": (NOW - timedelta(days=2, hours=-1)).isoformat()})
        log_event(db, t_rej, ulf, TaskEventType.REJECT, {"reason": "Student ill today"})

        total = db.query(Task).count()
        print(f"[SEED] tasks in DB after seeding: {total}")


# --------- CLI ---------
def main():
    parser = argparse.ArgumentParser(description="Reset/seed test data without deleting app.db")
    parser.add_argument("--reset", action="store_true",
                        help="Soft reset schema: drop_all + create_all before seeding")
    parser.add_argument("--hard", action="store_true",
                        help="Hard reset: attempt to delete SQLite file; falls back to soft if locked")
    parser.add_argument("--show", action="store_true",
                        help="Show DB target path and exit")
    args = parser.parse_args()

    if args.show:
        _log_db_target("SHOW")
        return

    if args.reset and args.hard:
        print("[WARN] --reset and --hard both given; using --hard")
        args.reset = False

    if args.reset or args.hard:
        reset_db(hard=args.hard)
    else:
        # sørg for at tabeller finnes hvis dette er første kjøring
        Base.metadata.create_all(bind=engine)

    seed()
    print("Seed (TEST) complete.")


if __name__ == "__main__":
    main()
