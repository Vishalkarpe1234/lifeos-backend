from sqlalchemy import String, Integer, Text, ForeignKey, JSON, Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date
from app.core.database import Base
from app.models.base_model import TimestampMixin


class ResearchPublication(TimestampMixin, Base):
    __tablename__ = "research_publications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    authors: Mapped[list] = mapped_column(JSON, default=list)
    journal_name: Mapped[str | None] = mapped_column(String(300))
    conference_name: Mapped[str | None] = mapped_column(String(300))
    publisher: Mapped[str | None] = mapped_column(String(300))
    doi: Mapped[str | None] = mapped_column(String(200))
    issn: Mapped[str | None] = mapped_column(String(50))
    isbn: Mapped[str | None] = mapped_column(String(50))
    volume: Mapped[str | None] = mapped_column(String(50))
    issue: Mapped[str | None] = mapped_column(String(50))
    pages: Mapped[str | None] = mapped_column(String(50))
    year: Mapped[int | None] = mapped_column(Integer)
    publication_date: Mapped[date | None] = mapped_column(Date)
    pub_type: Mapped[str] = mapped_column(String(50), default="journal")
    status: Mapped[str] = mapped_column(String(50), default="published")
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    index_type: Mapped[str | None] = mapped_column(String(100))
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    pdf_url: Mapped[str | None] = mapped_column(String(500))
    external_url: Mapped[str | None] = mapped_column(String(500))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    bibtex: Mapped[str | None] = mapped_column(Text)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)


class Conference(TimestampMixin, Base):
    __tablename__ = "conferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    website: Mapped[str | None] = mapped_column(String(500))
    paper_title: Mapped[str | None] = mapped_column(String(500))
    presentation_type: Mapped[str] = mapped_column(String(100), default="oral")
    status: Mapped[str] = mapped_column(String(50), default="presented")
    notes: Mapped[str | None] = mapped_column(Text)
    certificate_url: Mapped[str | None] = mapped_column(String(500))
