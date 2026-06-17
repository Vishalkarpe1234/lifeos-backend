from sqlalchemy import String, Integer, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base_model import TimestampMixin


class CodeSnippet(TimestampMixin, Base):
    __tablename__ = "code_snippets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(50), default="python")
    code: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
