from sqlalchemy import String, Integer, Text, JSON, Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date
from app.core.database import Base
from app.models.base_model import TimestampMixin


class JournalEntry(TimestampMixin, Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    mood: Mapped[str | None] = mapped_column(String(50))
    mood_score: Mapped[int | None] = mapped_column(Integer)
    energy_level: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    weather: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(255))
    is_private: Mapped[bool] = mapped_column(Boolean, default=True)
    images: Mapped[list] = mapped_column(JSON, default=list)
    gratitude: Mapped[list] = mapped_column(JSON, default=list)
    goals_tomorrow: Mapped[list] = mapped_column(JSON, default=list)
    highlights: Mapped[list] = mapped_column(JSON, default=list)
