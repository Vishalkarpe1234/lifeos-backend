from sqlalchemy import String, Integer, Text, JSON, Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date
from app.core.database import Base
from app.models.base_model import TimestampMixin


class Subject(TimestampMixin, Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50))
    semester: Mapped[str | None] = mapped_column(String(50))
    academic_year: Mapped[str | None] = mapped_column(String(20))
    branch: Mapped[str | None] = mapped_column(String(100))
    credits: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    syllabus_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    units: Mapped[list] = mapped_column(JSON, default=list)


class LecturePlan(TimestampMixin, Base):
    __tablename__ = "lecture_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subject_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_no: Mapped[str | None] = mapped_column(String(20))
    unit_title: Mapped[str | None] = mapped_column(String(255))
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    sub_topics: Mapped[list] = mapped_column(JSON, default=list)
    lecture_date: Mapped[date | None] = mapped_column(Date)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=50)
    objectives: Mapped[str | None] = mapped_column(Text)
    teaching_aids: Mapped[list] = mapped_column(JSON, default=list)
    notes_url: Mapped[str | None] = mapped_column(String(500))
    ppt_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="planned")
    remarks: Mapped[str | None] = mapped_column(Text)


class Assignment(TimestampMixin, Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subject_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    questions: Mapped[list] = mapped_column(JSON, default=list)
    due_date: Mapped[date | None] = mapped_column(Date)
    max_marks: Mapped[int | None] = mapped_column(Integer)
    document_url: Mapped[str | None] = mapped_column(String(500))
    academic_year: Mapped[str | None] = mapped_column(String(20))
    semester: Mapped[str | None] = mapped_column(String(50))


class QuestionBank(TimestampMixin, Base):
    __tablename__ = "question_banks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subject_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_no: Mapped[str | None] = mapped_column(String(20))
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(50), default="short")
    marks: Mapped[int | None] = mapped_column(Integer)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    answer: Mapped[str | None] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSON, default=list)
    correct_option: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    year: Mapped[int | None] = mapped_column(Integer)
