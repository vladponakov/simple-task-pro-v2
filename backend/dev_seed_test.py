import os
import time
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session

from app.db import Base, engine, SessionLocal
from app.models import User, Role, Student, Absence, Task, TaskStatus
from app.models import TaskEventType
from app.utils import log_event

from datetime import datetime, date
TODAY = date.today()
NOW   = datetime.now().replace(minute=0, second=0, microsecond=0)


# --- Robust reset that doesn't require deleting the SQLite file ---
def reset_db(hard: bool = False):
    """
    Robust reset:
    - Default (hard=False): drop_all + create_all (keeps app.db; avoids Windows file locks).
    - Hard (hard=True): try deleting app.db with retry; if locked, fall back to drop_all.
    """
    try:
        engine.dispose()  # close pooled connections
    except Exception:
        pass

    if not hard:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return

    # Hard reset path
    db_path = "app.db"
    if os.path.exists(db_path):
        for _ in range(8):  # ~4 seconds of retries
            try:
                os.remove(db_path)
                break
            except PermissionError:
                time.sleep(0.5)

        # If still locked, fall back to soft reset
        if os.path.exists(db_path):
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            return

    # Rebuild empty DB file
    Base.metadata.create_all(bind=engine)


def seed():
    db: Session = SessionLocal()

    # ===== Users (4) =====
    anna = User(name="Anna Admin", role=Role.ADMIN)   # Admin
    ulf  = User(name="Ulf",        role=Role.USER)    # User 1
    una  = User(name="Una",        role=Role.USER)    # User 2
    liam = User(name="Liam",       role=Role.USER)    # User 3 (extra for login testing)
    db.add_all([anna, ulf, una, liam]); db.commit()
    db.refresh(anna); db.refresh(ulf); db.refresh(una); db.refresh(liam)

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

    # ===== Absence history (varied reasons) =====
    db.add_all([
        Absence(student_id=s1.id, date=TODAY - timedelta(days=2), reason_code="Syk",   note="Fever",           reported_by="Teacher"),
        Absence(student_id=s1.id, date=TODAY - timedelta(days=1), reason_code="Syk",   note="Recovering",      reported_by="Teacher"),
        Absence(student_id=s2.id, date=TODAY - timedelta(days=3), reason_code="Reise", note="Family visit",    reported_by="Admin"),
        Absence(student_id=s3.id, date=TODAY - timedelta(days=9), reason_code="Annet", note="Doctor visit",    reported_by="Teacher"),
        Absence(student_id=s4.id, date=TODAY - timedelta(days=7), reason_code="Syk",   note="Cold",            reported_by="Teacher"),
        Absence(student_id=s5.id, date=TODAY - timedelta(days=6), reason_code="Reise", note="Competition",     reported_by="Admin"),
        Absence(student_id=s6.id, date=TODAY,                    reason_code="Syk",   note="Headache",         reported_by="Teacher"),
        Absence(student_id=s7.id, date=TODAY - timedelta(days=4), reason_code="Annet", note="Moving",           reported_by="Admin"),
        Absence(student_id=s8.id, date=TODAY - timedelta(days=1), reason_code="Syk",   note="Flu suspicion",    reported_by="Teacher"),
        Absence(student_id=s9.id, date=TODAY - timedelta(days=12),reason_code="Annet", note="Dentist",          reported_by="Teacher"),
    ])
    db.commit()

    # ===== Tasks for TODAY (smart route test for User1 & User2) =====
    def due(hh): return datetime(TODAY.year, TODAY.month, TODAY.day, hh, 0, 0)

    # --- User 1 (Ulf): 2 active visits today + 1 REJECTED + 1 DONE earlier this week
    t1 = Task(student_id=s1.id, title="Home visit: Oliver Smith",
              body="Verify homework plan; discuss recent absence.",
              address=s1.address, checklist=[{"text":"Knock the door","done":False},{"text":"Check absence notes","done":False}],
              due_at=due(10), status=TaskStatus.ASSIGNED, assignee_user_id=ulf.id, created_by=anna.id)

    t2 = Task(student_id=s2.id, title="Phone call: Amelia Johnson",
              body="Follow up on tardiness.", address=s2.address,
              checklist=[{"text":"Call guardian","done":False}], due_at=due(11),
              status=TaskStatus.ASSIGNED, assignee_user_id=ulf.id, created_by=anna.id)

    t3_done = Task(student_id=s1.id, title="Earlier visit: Oliver Smith",
              body="Weekly check", address=s1.address, checklist=[],
              due_at=NOW - timedelta(days=2), status=TaskStatus.DONE, assignee_user_id=ulf.id, created_by=anna.id)

    t_rej = Task(student_id=s8.id, title="Welfare check: Sophie Taylor",
              body="Confirm attendance tomorrow.", address=s8.address, checklist=[],
              due_at=due(14), status=TaskStatus.REJECTED, assignee_user_id=ulf.id, created_by=anna.id)

    # --- User 2 (Una): 3 visits today
    t4 = Task(student_id=s3.id, title="Home visit: Jack Williams",
              body="Collect consent form.", address=s3.address,
              checklist=[{"text":"Bring consent pack","done":False}], due_at=due(10),
              status=TaskStatus.ASSIGNED, assignee_user_id=una.id, created_by=anna.id)

    t5 = Task(student_id=s4.id, title="Parent meeting: Isla Brown",
              body="Behaviour plan discussion.", address=s4.address,
              checklist=[], due_at=due(12), status=TaskStatus.ASSIGNED, assignee_user_id=una.id, created_by=anna.id)

    t6 = Task(student_id=s5.id, title="Welfare check: Harry Jones",
              body="Follow up after absence.", address=s5.address,
              checklist=[], due_at=due(13), status=TaskStatus.ASSIGNED, assignee_user_id=una.id, created_by=anna.id)

    # --- New queue items (Admin should edit before assign)
    t_new1 = Task(student_id=s6.id, title="New: Emily Davis",
              body="Create visit plan.", address=s6.address, checklist=[{"text":"Draft plan","done":False}],
              due_at=due(15), status=TaskStatus.NEW, assignee_user_id=None, created_by=anna.id)

    t_new2 = Task(student_id=s7.id, title="New: George Miller",
              body="Initial contact.", address=s7.address, checklist=[],
              due_at=due(16), status=TaskStatus.NEW, assignee_user_id=None, created_by=anna.id)

    # --- Accepted example (User accepted earlier today)
    t_acc = Task(student_id=s9.id, title="Check-in: Noah Wilson",
              body="Short progress check.", address=s9.address, checklist=[],
              due_at=due(9), status=TaskStatus.ACCEPTED, assignee_user_id=una.id, created_by=anna.id)

    db.add_all([t1,t2,t3_done,t_rej,t4,t5,t6,t_new1,t_new2,t_acc]); db.commit()

    # ===== Audit trail =====
    for t in [t1,t2,t4,t5,t6,t_acc]:
        log_event(db, t, anna, TaskEventType.ASSIGN, {"to": t.assignee_user_id})
    log_event(db, t3_done, ulf, TaskEventType.COMPLETE, {"at": (NOW - timedelta(days=2, hours=-1)).isoformat()})
    log_event(db, t_rej, ulf, TaskEventType.REJECT, {"reason": "Student ill today"})
    # New tasks intentionally have no events to test admin edit+assign flow

    db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop & recreate tables (soft reset)")
    parser.add_argument("--hard", action="store_true", help="Try deleting app.db (with retry); falls back to soft")
    args = parser.parse_args()

    if args.reset or args.hard:
        reset_db(hard=args.hard)
    else:
        Base.metadata.create_all(bind=engine)

    seed()
    print("Seed (TEST) complete.")
