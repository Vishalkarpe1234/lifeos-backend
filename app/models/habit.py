from sqlalchemy import String, Integer, Text, JSON, Boolean, Date, Float
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date
from app.core.database import Base
from app.models.base_model import TimestampMixin


class Habit(TimestampMixin, Base):
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    category: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[str] = mapped_column(String(20), default="daily")
    frequency_days: Mapped[list] = mapped_column(JSON, default=list)
    target_count: Mapped[int] = mapped_column(Integer, default=1)
    unit: Mapped[str | None] = mapped_column(String(50))
    reminder_time: Mapped[str | None] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    streak_current: Mapped[int] = mapped_column(Integer, default=0)
    streak_longest: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[date | None] = mapped_column(Date)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class HabitLog(TimestampMixin, Base):
    __tablename__ = "habit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    habit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=1)
    value: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    mood: Mapped[str | None] = mapped_column(String(50))
    is_completed: Mapped[bool] = mapped_column(Boolean, default=True)
