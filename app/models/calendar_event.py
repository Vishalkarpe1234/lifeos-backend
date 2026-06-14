from sqlalchemy import String, Integer, Text, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
from datetime import datetime
from app.core.database import Base
from app.models.base_model import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class CalendarEvent(TimestampMixin, Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    category: Mapped[str] = mapped_column(String(50), default="general")
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=30)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
