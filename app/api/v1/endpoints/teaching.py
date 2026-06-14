from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.teaching import Subject, LecturePlan, Assignment, QuestionBank

router = APIRouter(prefix="/teaching", tags=["teaching"])


# ── Subjects ──────────────────────────────────────────────────────────────────

@router.get("/subjects/")
async def list_subjects(
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(Subject)
    if is_active is not None:
        q = q.where(Subject.is_active == is_active)
    offset = (page - 1) * page_size
    result = await db.execute(q.offset(offset).limit(page_size))
    subjects = result.scalars().all()
    total = (await db.execute(select(func.count()).select_from(Subject))).scalar_one()
    return {"items": [_subject_dict(s) for s in subjects], "total": total, "page": page, "page_size": page_size}


@router.post("/subjects/", status_code=status.HTTP_201_CREATED)
async def create_subject(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    subject = Subject(
        name=data.get("name", ""),
        code=data.get("code"),
        semester=data.get("semester"),
        academic_year=data.get("academic_year"),
        branch=data.get("branch"),
        credits=data.get("credits"),
        description=data.get("description"),
        syllabus_url=data.get("syllabus_url"),
        is_active=data.get("is_active", True),
        units=data.get("units", []),
    )
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return _subject_dict(subject)


@router.get("/subjects/{subject_id}")
async def get_subject(subject_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return _subject_dict(await _get_subject_or_404(subject_id, db))


@router.put("/subjects/{subject_id}")
async def update_subject(subject_id: int, data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    subject = await _get_subject_or_404(subject_id, db)
    for k, v in data.items():
        if hasattr(subject, k):
            setattr(subject, k, v)
    await db.commit()
    await db.refresh(subject)
    return _subject_dict(subject)


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(subject_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    subject = await _get_subject_or_404(subject_id, db)
    await db.delete(subject)
    await db.commit()


# ── Lecture Plans ──────────────────────────────────────────────────────────────

@router.get("/lecture-plans/")
async def list_lecture_plans(
    subject_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(LecturePlan)
    if subject_id:
        q = q.where(LecturePlan.subject_id == subject_id)
    if status:
        q = q.where(LecturePlan.status == status)
    offset = (page - 1) * page_size
    result = await db.execute(q.offset(offset).limit(page_size))
    plans = result.scalars().all()
    total = (await db.execute(select(func.count()).select_from(LecturePlan))).scalar_one()
    return {"items": [_plan_dict(p) for p in plans], "total": total, "page": page, "page_size": page_size}


@router.post("/lecture-plans/", status_code=status.HTTP_201_CREATED)
async def create_lecture_plan(data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    plan = LecturePlan(
        subject_id=data.get("subject_id"),
        subject_name=data.get("subject_name", ""),
        unit_no=data.get("unit_no"),
        unit_title=data.get("unit_title"),
        topic=data.get("topic", ""),
        sub_topics=data.get("sub_topics", []),
        duration_minutes=data.get("duration_minutes", 50),
        objectives=data.get("objectives"),
        teaching_aids=data.get("teaching_aids", []),
        notes_url=data.get("notes_url"),
        ppt_url=data.get("ppt_url"),
        status=data.get("status", "planned"),
        remarks=data.get("remarks"),
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return _plan_dict(plan)


@router.get("/lecture-plans/{plan_id}")
async def get_lecture_plan(plan_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return _plan_dict(await _get_plan_or_404(plan_id, db))


@router.put("/lecture-plans/{plan_id}")
async def update_lecture_plan(plan_id: int, data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    plan = await _get_plan_or_404(plan_id, db)
    for k, v in data.items():
        if hasattr(plan, k):
            setattr(plan, k, v)
    await db.commit()
    await db.refresh(plan)
    return _plan_dict(plan)


@router.delete("/lecture-plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lecture_plan(plan_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    plan = await _get_plan_or_404(plan_id, db)
    await db.delete(plan)
    await db.commit()


# ── Assignments ────────────────────────────────────────────────────────────────

@router.get("/assignments/")
async def list_assignments(
    subject_name: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(Assignment)
    if subject_name:
        q = q.where(Assignment.subject_name.ilike(f"%{subject_name}%"))
    offset = (page - 1) * page_size
    result = await db.execute(q.offset(offset).limit(page_size))
    assignments = result.scalars().all()
    total = (await db.execute(select(func.count()).select_from(Assignment))).scalar_one()
    return {"items": [_assignment_dict(a) for a in assignments], "total": total, "page": page, "page_size": page_size}


@router.post("/assignments/", status_code=status.HTTP_201_CREATED)
async def create_assignment(data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    from datetime import date as date_type
    assignment = Assignment(
        subject_name=data.get("subject_name", ""),
        title=data.get("title", ""),
        description=data.get("description"),
        questions=data.get("questions", []),
        due_date=date_type.fromisoformat(data["due_date"]) if data.get("due_date") else None,
        max_marks=data.get("max_marks"),
        document_url=data.get("document_url"),
        academic_year=data.get("academic_year"),
        semester=data.get("semester"),
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return _assignment_dict(assignment)


@router.put("/assignments/{assignment_id}")
async def update_assignment(assignment_id: int, data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    result = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    for k, v in data.items():
        if hasattr(assignment, k):
            setattr(assignment, k, v)
    await db.commit()
    await db.refresh(assignment)
    return _assignment_dict(assignment)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(assignment_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    result = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await db.delete(assignment)
    await db.commit()


# ── Question Bank ──────────────────────────────────────────────────────────────

@router.get("/question-bank/")
async def list_questions(
    subject_name: Optional[str] = None,
    question_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(QuestionBank)
    if subject_name:
        q = q.where(QuestionBank.subject_name.ilike(f"%{subject_name}%"))
    if question_type:
        q = q.where(QuestionBank.question_type == question_type)
    offset = (page - 1) * page_size
    result = await db.execute(q.offset(offset).limit(page_size))
    questions = result.scalars().all()
    total = (await db.execute(select(func.count()).select_from(QuestionBank))).scalar_one()
    return {"items": [_question_dict(q) for q in questions], "total": total, "page": page, "page_size": page_size}


@router.post("/question-bank/", status_code=status.HTTP_201_CREATED)
async def create_question(data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    question = QuestionBank(
        subject_name=data.get("subject_name", ""),
        unit_no=data.get("unit_no"),
        question_text=data.get("question_text", ""),
        question_type=data.get("question_type", "short"),
        marks=data.get("marks"),
        difficulty=data.get("difficulty", "medium"),
        answer=data.get("answer"),
        options=data.get("options", []),
        correct_option=data.get("correct_option"),
        tags=data.get("tags", []),
        year=data.get("year"),
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return _question_dict(question)


@router.delete("/question-bank/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(question_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    result = await db.execute(select(QuestionBank).where(QuestionBank.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    await db.delete(question)
    await db.commit()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_subject_or_404(subject_id: int, db: AsyncSession) -> Subject:
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


async def _get_plan_or_404(plan_id: int, db: AsyncSession) -> LecturePlan:
    result = await db.execute(select(LecturePlan).where(LecturePlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Lecture plan not found")
    return plan


def _subject_dict(s: Subject) -> dict:
    return {
        "id": s.id, "name": s.name, "code": s.code, "semester": s.semester,
        "academic_year": s.academic_year, "branch": s.branch, "credits": s.credits,
        "description": s.description, "syllabus_url": s.syllabus_url,
        "is_active": s.is_active, "units": s.units,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _plan_dict(p: LecturePlan) -> dict:
    return {
        "id": p.id, "subject_id": p.subject_id, "subject_name": p.subject_name,
        "unit_no": p.unit_no, "unit_title": p.unit_title, "topic": p.topic,
        "sub_topics": p.sub_topics, "duration_minutes": p.duration_minutes,
        "objectives": p.objectives, "teaching_aids": p.teaching_aids,
        "notes_url": p.notes_url, "ppt_url": p.ppt_url, "status": p.status,
        "remarks": p.remarks,
        "lecture_date": p.lecture_date.isoformat() if p.lecture_date else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _assignment_dict(a: Assignment) -> dict:
    return {
        "id": a.id, "subject_name": a.subject_name, "title": a.title,
        "description": a.description, "questions": a.questions,
        "due_date": a.due_date.isoformat() if a.due_date else None,
        "max_marks": a.max_marks, "document_url": a.document_url,
        "academic_year": a.academic_year, "semester": a.semester,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _question_dict(q: QuestionBank) -> dict:
    return {
        "id": q.id, "subject_name": q.subject_name, "unit_no": q.unit_no,
        "question_text": q.question_text, "question_type": q.question_type,
        "marks": q.marks, "difficulty": q.difficulty, "answer": q.answer,
        "options": q.options, "correct_option": q.correct_option,
        "tags": q.tags, "year": q.year,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }
