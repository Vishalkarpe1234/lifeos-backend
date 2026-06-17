from sqlalchemy import String, Integer, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date, datetime
from app.core.database import Base
from app.models.base_model import TimestampMixin


class FocusSession(TimestampMixin, Base):
    __tablename__ = "focus_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    rounds_completed: Mapped[int] = mapped_column(Integer, default=1)
    focus_type: Mapped[str] = mapped_column(String(50), default="pomodoro")
    date: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
