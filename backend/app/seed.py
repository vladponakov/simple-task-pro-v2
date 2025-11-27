from __future__ import annotations

from datetime import datetime, timedelta, date

from sqlalchemy.orm import Session

from app.db import Base, engine, SessionLocal
from app.models import (
    Absence,
    Role,
    Student,
    Task,
    TaskStatus,
    TaskEventType,
    User,
)
from app.utils import hash_password, log_event, create_home_visit_task_for_student
from app.config import settings

# -------------------------------------------------------------------
#  Raw data from your Excel sheet, converted once into Python.
#  (Year is stored in student_class, first+last -> name)
# -------------------------------------------------------------------
STUDENT_ROWS = [
    {'year': 11, 'first_name': 'Masooma', 'last_name': 'Abbas', 'gender': 'F', 'address': 'Flat 13, Dodsley Place 289 Montagu Road, London, N9 0HU', 'contact_name': 'Abbas', 'contact_relationship': 'Mother', 'contact_phone': '07700 900001', 'absent_today': True, 'attendance_ytd': 94.0, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 94.74, 'attendance_last_3_weeks': 79.31, 'attendance_last_4_weeks': 84.62},
    {'year': 11, 'first_name': 'Zahara', 'last_name': 'Abbott', 'gender': 'F', 'address': '64 Richmond Crescent, Edmonton, London, N9 7QJ', 'contact_name': 'Abbott', 'contact_relationship': 'Mother', 'contact_phone': '07700 900002', 'absent_today': True, 'attendance_ytd': 92.0, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 84.21, 'attendance_last_3_weeks': 89.66, 'attendance_last_4_weeks': 87.18},
    {'year': 11, 'first_name': 'Savt', 'last_name': 'Abejuro', 'gender': 'M', 'address': '11 Tramway Avenue, London, N9 8PD', 'contact_name': 'Abejuro', 'contact_relationship': 'Mother', 'contact_phone': '07700 900003', 'absent_today': True, 'attendance_ytd': 75.0, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 80.0, 'attendance_last_3_weeks': 80.0, 'attendance_last_4_weeks': 75.0},
    {'year': 11, 'first_name': 'Laura', 'last_name': 'Abejuro', 'gender': 'M', 'address': '29 Somerset Road, London, N18 1HH', 'contact_name': 'Abejuro', 'contact_relationship': 'Mother', 'contact_phone': '07700 900004', 'absent_today': True, 'attendance_ytd': 43.0, 'attendance_last_week': 40.0, 'attendance_last_2_weeks': 57.89, 'attendance_last_3_weeks': 65.52, 'attendance_last_4_weeks': 69.23},
    {'year': 11, 'first_name': 'Herman', 'last_name': 'Abejuro', 'gender': 'F', 'address': '71 Folkestone Road, London, N18 2ER', 'contact_name': 'Abejuro', 'contact_relationship': 'Father', 'contact_phone': '07700 900005', 'absent_today': True, 'attendance_ytd': 82.0, 'attendance_last_week': 60.0, 'attendance_last_2_weeks': 73.68, 'attendance_last_3_weeks': 82.76, 'attendance_last_4_weeks': 87.18},
    {'year': 11, 'first_name': 'Henry', 'last_name': 'Abejurouge', 'gender': 'M', 'address': '57 Hudson Way, London, N9 0XE', 'contact_name': 'Abejurouge', 'contact_relationship': 'Mother', 'contact_phone': '07700 900006', 'absent_today': True, 'attendance_ytd': 93.0, 'attendance_last_week': 90.0, 'attendance_last_2_weeks': 85.0, 'attendance_last_3_weeks': 90.0, 'attendance_last_4_weeks': 92.5},
    {'year': 11, 'first_name': 'Richard', 'last_name': 'Aberdeen', 'gender': 'F', 'address': '165 Bounces Road, London, N9 8LL', 'contact_name': 'Aberdeen', 'contact_relationship': 'Father', 'contact_phone': '07700 900007', 'absent_today': True, 'attendance_ytd': 100.0, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 94.74, 'attendance_last_3_weeks': 96.55, 'attendance_last_4_weeks': 97.44},
    {'year': 10, 'first_name': 'Anbigale', 'last_name': 'Ableson', 'gender': 'F', 'address': 'Flat 14, Well House Beaconsfield Road, London, N9 0EB', 'contact_name': 'Ableson', 'contact_relationship': 'Mother', 'contact_phone': '07700 900008', 'absent_today': True, 'attendance_ytd': 70.41, 'attendance_last_week': 0.0, 'attendance_last_2_weeks': 10.0, 'attendance_last_3_weeks': 33.33, 'attendance_last_4_weeks': 50.0},
    {'year': 10, 'first_name': 'Jenny', 'last_name': 'Acton', 'gender': 'M', 'address': '55 Alexandra Road, Hemel Hempstead, HP2 4AQ', 'contact_name': 'Acton', 'contact_relationship': 'Father', 'contact_phone': '07700 900009', 'absent_today': True, 'attendance_ytd': 83.67, 'attendance_last_week': 80.0, 'attendance_last_2_weeks': 50.0, 'attendance_last_3_weeks': 63.33, 'attendance_last_4_weeks': 70.0},
    {'year': 9, 'first_name': 'Alander', 'last_name': 'Adam', 'gender': 'F', 'address': '61 St. Alphege Road, London, N9 8BU', 'contact_name': 'Adam', 'contact_relationship': 'Father', 'contact_phone': '07700 900010', 'absent_today': True, 'attendance_ytd': 93.88, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 90.0, 'attendance_last_3_weeks': 93.33, 'attendance_last_4_weeks': 95.0},
    {'year': 9, 'first_name': 'Stanley', 'last_name': 'Adam', 'gender': 'M', 'address': '140 Bulwer Road, Edmonton, London, N18 1QQ', 'contact_name': 'Adam', 'contact_relationship': 'Father', 'contact_phone': '07700 900011', 'absent_today': True, 'attendance_ytd': 93.88, 'attendance_last_week': 60.0, 'attendance_last_2_weeks': 70.0, 'attendance_last_3_weeks': 80.0, 'attendance_last_4_weeks': 80.0},
    {'year': 9, 'first_name': 'Mahmood', 'last_name': 'Adnan', 'gender': 'M', 'address': '22 Morley Avenue, Edmonton, London, N18 2QT', 'contact_name': 'Adnan', 'contact_relationship': 'Mother', 'contact_phone': '07700 900012', 'absent_today': True, 'attendance_ytd': 91.84, 'attendance_last_week': 80.0, 'attendance_last_2_weeks': 80.0, 'attendance_last_3_weeks': 86.67, 'attendance_last_4_weeks': 85.0},
    {'year': 9, 'first_name': 'Oliver', 'last_name': 'Afsal', 'gender': 'M', 'address': '18 Brettenham Road, London, N18 2ET', 'contact_name': 'Afsal', 'contact_relationship': 'Mother', 'contact_phone': '07700 900013', 'absent_today': True, 'attendance_ytd': 29.59, 'attendance_last_week': 0.0, 'attendance_last_2_weeks': 0.0, 'attendance_last_3_weeks': 0.0, 'attendance_last_4_weeks': 0.0},
    {'year': 9, 'first_name': 'Hosaib', 'last_name': 'Agha', 'gender': 'M', 'address': '45 Gordon Road, Edmonton, London, N9 0LX', 'contact_name': 'Agha', 'contact_relationship': 'Father', 'contact_phone': '07700 900014', 'absent_today': True, 'attendance_ytd': 91.84, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 90.0, 'attendance_last_3_weeks': 93.33, 'attendance_last_4_weeks': 95.0},
    {'year': 9, 'first_name': 'Hosiab', 'last_name': 'Agha', 'gender': 'F', 'address': '78 Town Road, Edmonton, London, N9 0RG', 'contact_name': 'Agha', 'contact_relationship': 'Mother', 'contact_phone': '07700 900015', 'absent_today': True, 'attendance_ytd': 93.88, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 80.0, 'attendance_last_3_weeks': 86.67, 'attendance_last_4_weeks': 90.0},
    {'year': 9, 'first_name': 'Shohaib', 'last_name': 'Agha', 'gender': 'M', 'address': 'Flat 1, 395 Montagu Road, London, N9 0HP', 'contact_name': 'Agha', 'contact_relationship': 'Mother', 'contact_phone': '07700 900016', 'absent_today': True, 'attendance_ytd': 85.71, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 60.0, 'attendance_last_3_weeks': 73.33, 'attendance_last_4_weeks': 80.0},
    {'year': 9, 'first_name': 'Asif', 'last_name': 'Ahaz', 'gender': 'M', 'address': '179 Hertford Road, London, N9 7EP', 'contact_name': 'Ahaz', 'contact_relationship': 'Mother', 'contact_phone': '07700 900017', 'absent_today': True, 'attendance_ytd': 91.84, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 94.74, 'attendance_last_3_weeks': 82.76, 'attendance_last_4_weeks': 82.05},
    {'year': 9, 'first_name': 'DJ', 'last_name': 'Ahmed', 'gender': 'F', 'address': '179 Hertford Road, London, N9 7EP', 'contact_name': 'Ahmed', 'contact_relationship': 'Mother', 'contact_phone': '07700 900018', 'absent_today': True, 'attendance_ytd': 91.84, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 94.74, 'attendance_last_3_weeks': 82.76, 'attendance_last_4_weeks': 82.05},
    {'year': 8, 'first_name': 'Wasim', 'last_name': 'Ahmed', 'gender': 'F', 'address': "38 St. Mary's Road, London, N9 8NJ", 'contact_name': 'Ahmed', 'contact_relationship': 'Mother', 'contact_phone': '07700 900019', 'absent_today': True, 'attendance_ytd': 100.0, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 90.0, 'attendance_last_3_weeks': 93.33, 'attendance_last_4_weeks': 95.0},
    {'year': 9, 'first_name': 'Asif', 'last_name': 'Ahmoud', 'gender': 'F', 'address': '391A Fore Street, London, N9 0NR', 'contact_name': 'Ahmoud', 'contact_relationship': 'Mother', 'contact_phone': '07700 900020', 'absent_today': True, 'attendance_ytd': 73.47, 'attendance_last_week': 0.0, 'attendance_last_2_weeks': 0.0, 'attendance_last_3_weeks': 6.67, 'attendance_last_4_weeks': 30.0},
    {'year': 10, 'first_name': 'Jason', 'last_name': 'Air', 'gender': 'M', 'address': '58 Hennessy Road, London, N9 0XJ', 'contact_name': 'Air', 'contact_relationship': 'Mother', 'contact_phone': '07700 900021', 'absent_today': True, 'attendance_ytd': 36.73, 'attendance_last_week': 0.0, 'attendance_last_2_weeks': 0.0, 'attendance_last_3_weeks': 6.67, 'attendance_last_4_weeks': 25.0},
    {'year': 10, 'first_name': 'Matthew', 'last_name': 'Alderson', 'gender': 'F', 'address': '27 Oxford Road, London, N9 0LY', 'contact_name': 'Alderson', 'contact_relationship': 'Father', 'contact_phone': '07700 900022', 'absent_today': True, 'attendance_ytd': 95.92, 'attendance_last_week': 80.0, 'attendance_last_2_weeks': 80.0, 'attendance_last_3_weeks': 86.67, 'attendance_last_4_weeks': 90.0},
    {'year': 11, 'first_name': 'Kristina', 'last_name': 'Aldridge', 'gender': 'M', 'address': '107 Brick Lane, Enfield, EN1 3PP', 'contact_name': 'Aldridge', 'contact_relationship': 'Mother', 'contact_phone': '07700 900023', 'absent_today': True, 'attendance_ytd': 80.65, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 89.47, 'attendance_last_3_weeks': 85.71, 'attendance_last_4_weeks': 75.0},
    {'year': 7, 'first_name': 'Jack', 'last_name': 'Alexander', 'gender': 'F', 'address': '140 Bulwer Road, Edmonton, London, N18 1QQ', 'contact_name': 'Alexander', 'contact_relationship': 'Father', 'contact_phone': '07700 900024', 'absent_today': True, 'attendance_ytd': 98.0, 'attendance_last_week': 80.0, 'attendance_last_2_weeks': 80.0, 'attendance_last_3_weeks': 86.67, 'attendance_last_4_weeks': 90.0},
    {'year': 7, 'first_name': 'Ashiq', 'last_name': 'Alexander', 'gender': 'F', 'address': '18 Brettenham Road, London, N18 2ET', 'contact_name': 'Alexander', 'contact_relationship': 'Mother', 'contact_phone': '07700 900025', 'absent_today': True, 'attendance_ytd': 84.0, 'attendance_last_week': 80.0, 'attendance_last_2_weeks': 60.0, 'attendance_last_3_weeks': 73.33, 'attendance_last_4_weeks': 75.0},
    {'year': 7, 'first_name': 'Claire', 'last_name': 'Alexander', 'gender': 'M', 'address': '6A College Close, Edmonton, London, N18 2XS', 'contact_name': 'Alexander', 'contact_relationship': 'Mother', 'contact_phone': '07700 900026', 'absent_today': True, 'attendance_ytd': 89.0, 'attendance_last_week': 100.0, 'attendance_last_2_weeks': 85.0, 'attendance_last_3_weeks': 83.33, 'attendance_last_4_weeks': 87.5},
    {'year': 7, 'first_name': 'Anthony', 'last_name': 'Alfred', 'gender': 'M', 'address': '18 Jeremys Green, London, N18 2NB', 'contact_name': 'Alfred', 'contact_relationship': 'Mother', 'contact_phone': '07700 900027', 'absent_today': True, 'attendance_ytd': 72.0, 'attendance_last_week': 0.0, 'attendance_last_2_weeks': 0.0, 'attendance_last_3_weeks': 6.67, 'attendance_last_4_weeks': 25.0},
    {'year': 11, 'first_name': 'Aisha', 'last_name': 'Ali', 'gender': 'F', 'address': '71 Sheldon Road, London, N18 1RQ', 'contact_name': 'Ali', 'contact_relationship': 'Mother', 'contact_phone': '07700 900028', 'absent_today': True, 'attendance_ytd': 82.0, 'attendance_last_week': 60.0, 'attendance_last_2_weeks': 63.16, 'attendance_last_3_weeks': 62.07, 'attendance_last_4_weeks': 71.79},
    {'year': 9, 'first_name': 'Hannah', 'last_name': 'Ali', 'gender': 'M', 'address': '4 Byron Terrace Hertford Road, London, N9 7DG', 'contact_name': 'Ali', 'contact_relationship': 'Mother', 'contact_phone': '07700 900029', 'absent_today': True, 'attendance_ytd': 93.55, 'attendance_last_week': 80.0, 'attendance_last_2_weeks': 84.21, 'attendance_last_3_weeks': 89.66, 'attendance_last_4_weeks': 87.18},
]


def reset_db() -> None:
    print("[RESET] drop_all + create_all")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_minimal(db: Session) -> None:
    # --- Users ---
    admin = User(
        name="Paddy MacGrath",
        email="paddy@example.com",
        role=Role.ADMIN,
        password_hash=hash_password("admin123"),
    )
    ulf = User(
        name="Ulf",
        email="ulf@example.com",
        role=Role.USER,
        password_hash=hash_password("user1"),
    )
    una = User(
        name="Una",
        email="una@example.com",
        role=Role.USER,
        password_hash=hash_password("user2"),
    )

    db.add_all([admin, ulf, una])
    db.commit()
    db.refresh(admin)
    db.refresh(ulf)
    db.refresh(una)

    print(f"[SEED] Users created: admin={admin.id}, ulf={ulf.id}, una={una.id}")

    # --- Students from STUDENT_ROWS ---
    students: list[Student] = []
    for row in STUDENT_ROWS:
        student = Student(
            name=f"{row['first_name']} {row['last_name']}",
            student_class=str(row["year"]),
            address=row["address"],
            gender=row["gender"],
            contact_name=row["contact_name"],
            contact_relationship=row["contact_relationship"],
            contact_phone=row["contact_phone"],
            absent_today=row["absent_today"],
            attendance_ytd=row["attendance_ytd"],
            attendance_last_week=row["attendance_last_week"],
            attendance_last_2_weeks=row["attendance_last_2_weeks"],
            attendance_last_3_weeks=row["attendance_last_3_weeks"],
            attendance_last_4_weeks=row["attendance_last_4_weeks"],
        )
        db.add(student)
        students.append(student)

    db.commit()
    for s in students:
        db.refresh(s)

    print(f"[SEED] Created {len(students)} students")

    # --- Tasks for today (one per student) ---
    today = datetime.utcnow().date()
    tasks: list[Task] = []
    for i, s in enumerate(students, start=1):
        assignee = ulf if i % 2 == 1 else una

        due_dt = datetime.combine(
            today,
            datetime.min.time(),
        ).replace(hour=9 + (i % 5))

        # Bruk samme helper som API/import:
        # - tittel = "FirstName LastName" / student.name
        # - body = "Home Visite" (default)
        # - status = NEW
        # - assignee = Ulf / Una
        task = create_home_visit_task_for_student(
            db,
            student=s,
            actor=admin,                      # admin er "created_by"
            body=None,                        # lar helper sette "Home Visite"
            assignee_user_id=assignee.id,
            due_at=due_dt,
            external_ref=None,
            checklist=[{"text": "Talk to guardian", "done": False}],
            attendance_pct=s.attendance_ytd,
        )
        tasks.append(task)
        log_event(db, task, admin, TaskEventType.EDIT, {"create": True})

    print(f"[SEED] Minimal: tasks={len(tasks)}")


def main(reset: bool = False) -> None:
    print(f"[SEED] DATABASE_URL: {settings.DATABASE_URL}")

    if reset:
        reset_db()

    db = SessionLocal()
    try:
        seed_minimal(db)
    finally:
        db.close()
    print("Seed complete.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset", action="store_true", help="Drop + recreate tables before seeding"
    )
    args = parser.parse_args()
    main(reset=args.reset)
