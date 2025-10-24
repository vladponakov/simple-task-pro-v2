import os
from datetime import datetime, date
from sqlalchemy.orm import Session

from app.db import Base, engine, SessionLocal
from app.models import User, Role, Student, Absence, Task, TaskStatus
from app.utils import log_event
from app.models import TaskEventType

def reset_db():
    if os.path.exists("app.db"):
        os.remove("app.db")
    Base.metadata.create_all(bind=engine)

def seed():
    db: Session = SessionLocal()

    # Users (English names)
    anna = User(name="Anna Admin", role=Role.ADMIN)
    ulf = User(name="Ulf", role=Role.USER)   # User 1
    una = User(name="Una", role=Role.USER)   # User 2
    db.add_all([anna, ulf, una]); db.commit()
    db.refresh(anna); db.refresh(ulf); db.refresh(una)

    # Students (London addresses - Google Maps friendly)
    s1 = Student(name="Oliver Smith", student_class="10B", address="221B Baker St, London")
    s2 = Student(name="Amelia Johnson", student_class="9A", address="10 Downing St, London")
    s3 = Student(name="Jack Williams", student_class="11C", address="Trafalgar Square, London")
    s4 = Student(name="Isla Brown", student_class="8D", address="1 Canada Square, London")
    s5 = Student(name="Harry Jones", student_class="7E", address="30 St Mary Axe, London")
    s6 = Student(name="Emily Davis", student_class="7F", address="Buckingham Palace, London")
    s7 = Student(name="George Miller", student_class="6A", address="Tower Bridge, London")
    db.add_all([s1,s2,s3,s4,s5,s6,s7]); db.commit()

    # Absence history examples
    db.add_all([
        Absence(student_id=s1.id, date=date(2025,10,17), reason_code="Syk", note="Fever", reported_by="Teacher"),
        Absence(student_id=s1.id, date=date(2025,10,18), reason_code="Syk", note="Recovering", reported_by="Teacher"),
        Absence(student_id=s2.id, date=date(2025,10,16), reason_code="Reise", note="Family visit", reported_by="Admin"),
        Absence(student_id=s3.id, date=date(2025,10,10), reason_code="Annet", note="Doctor appointment", reported_by="Teacher"),
        Absence(student_id=s4.id, date=date(2025,10,12), reason_code="Syk", note="Cold", reported_by="Teacher"),
        Absence(student_id=s5.id, date=date(2025,10,13), reason_code="Reise", note="Competition", reported_by="Admin"),
        Absence(student_id=s6.id, date=date(2025,10,19), reason_code="Syk", note="Headache", reported_by="Teacher"),
        Absence(student_id=s7.id, date=date(2025,10,15), reason_code="Annet", note="Moving", reported_by="Admin"),
    ])
    db.commit()

    # Tasks for 19 Oct 2025
    due = datetime(2025, 10, 19, 10, 0, 0)
    t1 = Task(student_id=s1.id, title="Home visit: Oliver Smith", body="Verify homework plan; discuss absence.", address=s1.address,
              checklist=[{"text":"Knock the door","done":False},{"text":"Check absence notes","done":False}], due_at=due,
              status=TaskStatus.ASSIGNED, assignee_user_id=ulf.id, created_by=anna.id)
    t2 = Task(student_id=s2.id, title="Phone call: Amelia Johnson", body="Follow up on tardiness.", address=s2.address,
              checklist=[{"text":"Call guardian","done":False}], due_at=due.replace(hour=11),
              status=TaskStatus.ASSIGNED, assignee_user_id=ulf.id, created_by=anna.id)
    t3 = Task(student_id=s1.id, title="Earlier visit: Oliver Smith", body="Week task", address=s1.address,
              checklist=[], due_at=datetime(2025,10,17,9,0,0),
              status=TaskStatus.DONE, assignee_user_id=ulf.id, created_by=anna.id)
    t4 = Task(student_id=s3.id, title="Home visit: Jack Williams", body="Collect consent form.", address=s3.address,
              checklist=[], due_at=due, status=TaskStatus.ASSIGNED, assignee_user_id=una.id, created_by=anna.id)
    t5 = Task(student_id=s4.id, title="Parent meeting: Isla Brown", body="Behaviour plan.", address=s4.address,
              checklist=[], due_at=due.replace(hour=12), status=TaskStatus.ASSIGNED, assignee_user_id=una.id, created_by=anna.id)
    t6 = Task(student_id=s5.id, title="Welfare check: Harry Jones", body="Check after absence note.", address=s5.address,
              checklist=[], due_at=due.replace(hour=13), status=TaskStatus.ASSIGNED, assignee_user_id=una.id, created_by=anna.id)

    db.add_all([t1,t2,t3,t4,t5,t6]); db.commit()

    for t in [t1,t2,t4,t5,t6]:
        log_event(db, t, anna, TaskEventType.ASSIGN, {"to": t.assignee_user_id})
    log_event(db, t3, ulf, TaskEventType.COMPLETE, {"at": datetime(2025,10,17,10).isoformat()})

    db.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if args.reset:
        reset_db()
    else:
        from app.db import Base, engine
        Base.metadata.create_all(bind=engine)

    seed()
    print("Seed complete.")
