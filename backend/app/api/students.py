# ================================================================
# BLOCK: STUDENTS_ROUTER
# Purpose: list/create/delete + simple history endpoint
# ================================================================
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..db import SessionLocal
from ..models import Student, StudentHistory
from ..schemas import StudentCreate, StudentOut

router = APIRouter(prefix="/api/students", tags=["students"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.get("", response_model=List[StudentOut])
def list_students(db: Session = Depends(get_db)):
    return db.query(Student).order_by(Student.name.asc()).all()

@router.post("", response_model=StudentOut)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    s = Student(name=payload.name)
    db.add(s); db.commit(); db.refresh(s)
    return s

@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    s = db.query(Student).get(student_id)
    if not s:
        raise HTTPException(404, "Student not found")
    db.delete(s); db.commit()
    return {"ok": True}

@router.get("/{student_id}/history")
def student_history(student_id: int, db: Session = Depends(get_db)):
    return (
        db.query(StudentHistory)
          .filter(StudentHistory.student_id == student_id)
          .order_by(StudentHistory.created_at.desc())
          .all()
    )
