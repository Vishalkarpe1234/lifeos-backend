from sqlalchemy import String, Integer, Text, JSON, Boolean, Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date
from decimal import Decimal
from app.core.database import Base
from app.models.base_model import TimestampMixin


class ExpenseCategory(TimestampMixin, Base):
    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    type: Mapped[str] = mapped_column(String(20), default="expense")


class Expense(TimestampMixin, Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="expense")
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(100))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    receipt_url: Mapped[str | None] = mapped_column(String(500))
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence: Mapped[str | None] = mapped_column(String(50))


class Budget(TimestampMixin, Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    category_name: Mapped[str | None] = mapped_column(String(100))
    period: Mapped[str] = mapped_column(String(20), default="monthly")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    notes: Mapped[str | None] = mapped_column(Text)


class FinanceGoal(TimestampMixin, Base):
    __tablename__ = "finance_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    current_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    unit: Mapped[str | None] = mapped_column(String(50))
    target_date: Mapped[date | None] = mapped_column(Date)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    milestones: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
