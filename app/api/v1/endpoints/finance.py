from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, extract
from typing import Optional, List
from pydantic import BaseModel
from datetime import date
from decimal import Decimal

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.finance import Expense, ExpenseCategory, Budget, FinanceGoal as Goal
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/finance", tags=["Finance"])


class ExpenseCreate(BaseModel):
    title: str
    amount: Decimal
    type: str = "expense"
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    date: date
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = []
    is_recurring: bool = False
    recurrence: Optional[str] = None


class CategoryCreate(BaseModel):
    name: str
    icon: Optional[str] = None
    color: str = "#6366F1"
    type: str = "expense"


class BudgetCreate(BaseModel):
    name: str
    amount: Decimal
    category_name: Optional[str] = None
    period: str = "monthly"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    color: str = "#6366F1"
    notes: Optional[str] = None


class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    target_value: Optional[Decimal] = None
    current_value: Decimal = Decimal("0")
    unit: Optional[str] = None
    target_date: Optional[date] = None
    color: str = "#6366F1"
    tags: List[str] = []


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    items = (await db.execute(select(ExpenseCategory).order_by(ExpenseCategory.name))).scalars().all()
    return {"items": items}


@router.post("/categories", status_code=201)
async def create_category(data: CategoryCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    cat = ExpenseCategory(**data.model_dump())
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


@router.get("/expenses")
async def list_expenses(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    type: Optional[str] = None,
    category_name: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    filters = []
    if type:
        filters.append(Expense.type == type)
    if category_name:
        filters.append(Expense.category_name == category_name)
    if month:
        filters.append(extract("month", Expense.date) == month)
    if year:
        filters.append(extract("year", Expense.date) == year)

    query = select(Expense)
    count_q = select(func.count()).select_from(Expense)
    if filters:
        query = query.where(and_(*filters))
        count_q = count_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar()
    skip = (page - 1) * page_size
    items = (await db.execute(query.order_by(desc(Expense.date)).offset(skip).limit(page_size))).scalars().all()
    return {"items": items, "total": total, "page": page}


@router.post("/expenses", status_code=201)
async def create_expense(data: ExpenseCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    expense = Expense(**data.model_dump())
    db.add(expense)
    await db.flush()
    await db.refresh(expense)
    return expense


@router.put("/expenses/{expense_id}")
async def update_expense(expense_id: int, data: ExpenseCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    exp = (await db.execute(select(Expense).where(Expense.id == expense_id))).scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(exp, k, v)
    await db.flush()
    await db.refresh(exp)
    return exp


@router.delete("/expenses/{expense_id}", response_model=SuccessResponse)
async def delete_expense(expense_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    exp = (await db.execute(select(Expense).where(Expense.id == expense_id))).scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    await db.delete(exp)
    return SuccessResponse(message="Expense deleted")


@router.get("/budgets")
async def list_budgets(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    items = (await db.execute(select(Budget).order_by(Budget.name))).scalars().all()
    return {"items": items}


@router.post("/budgets", status_code=201)
async def create_budget(data: BudgetCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    budget = Budget(**data.model_dump())
    db.add(budget)
    await db.flush()
    await db.refresh(budget)
    return budget


@router.get("/goals")
async def list_goals(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    items = (await db.execute(select(Goal).order_by(Goal.is_completed, desc(Goal.created_at)))).scalars().all()
    return {"items": items}


@router.post("/goals", status_code=201)
async def create_goal(data: GoalCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    goal = Goal(**data.model_dump())
    db.add(goal)
    await db.flush()
    await db.refresh(goal)
    return goal


@router.patch("/goals/{goal_id}/update-progress")
async def update_goal_progress(goal_id: int, current_value: Decimal, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    goal = (await db.execute(select(Goal).where(Goal.id == goal_id))).scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal.current_value = current_value
    if goal.target_value and current_value >= goal.target_value:
        goal.is_completed = True
    await db.flush()
    return goal


@router.get("/stats")
async def finance_stats(
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    today = date.today()
    m = month or today.month
    y = year or today.year

    income = (await db.execute(
        select(func.sum(Expense.amount)).where(
            and_(extract("month", Expense.date) == m, extract("year", Expense.date) == y, Expense.type == "income")
        )
    )).scalar() or 0

    expense = (await db.execute(
        select(func.sum(Expense.amount)).where(
            and_(extract("month", Expense.date) == m, extract("year", Expense.date) == y, Expense.type == "expense")
        )
    )).scalar() or 0

    by_category = (await db.execute(
        select(Expense.category_name, func.sum(Expense.amount).label("total"))
        .where(and_(extract("month", Expense.date) == m, extract("year", Expense.date) == y, Expense.type == "expense"))
        .group_by(Expense.category_name)
        .order_by(desc("total"))
    )).all()

    return {
        "month": m,
        "year": y,
        "income": float(income),
        "expense": float(expense),
        "balance": float(income) - float(expense),
        "by_category": [{"category": r[0], "total": float(r[1])} for r in by_category],
    }
