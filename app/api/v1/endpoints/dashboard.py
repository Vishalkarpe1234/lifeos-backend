from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import date, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.task import Task
from app.models.habit import Habit, HabitLog
from app.models.note import Note
from app.models.finance import Expense
from app.models.research import ResearchPublication
from app.models.project import Project

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    tasks_today = (await db.execute(
        select(func.count()).select_from(Task).where(
            and_(Task.due_date == today, Task.is_completed == False)
        )
    )).scalar()

    tasks_completed_today = (await db.execute(
        select(func.count()).select_from(Task).where(
            and_(Task.due_date == today, Task.is_completed == True)
        )
    )).scalar()

    total_tasks = (await db.execute(select(func.count()).select_from(Task))).scalar()
    completed_tasks = (await db.execute(select(func.count()).select_from(Task).where(Task.is_completed == True))).scalar()

    total_notes = (await db.execute(select(func.count()).select_from(Note).where(Note.is_archived == False))).scalar()

    total_publications = (await db.execute(select(func.count()).select_from(ResearchPublication))).scalar()

    active_projects = (await db.execute(
        select(func.count()).select_from(Project).where(Project.status == "active")
    )).scalar()

    month_start = today.replace(day=1)
    monthly_expense = (await db.execute(
        select(func.sum(Expense.amount)).where(
            and_(Expense.date >= month_start, Expense.type == "expense")
        )
    )).scalar() or 0

    active_habits = (await db.execute(
        select(func.count()).select_from(Habit).where(Habit.is_active == True)
    )).scalar()

    habits_done_today = (await db.execute(
        select(func.count()).select_from(HabitLog).where(
            and_(HabitLog.date == today, HabitLog.is_completed == True)
        )
    )).scalar()

    recent_tasks = (await db.execute(
        select(Task).where(Task.is_completed == False).order_by(Task.due_date.asc().nullslast()).limit(5)
    )).scalars().all()

    recent_notes = (await db.execute(
        select(Note).where(Note.is_archived == False).order_by(desc(Note.updated_at)).limit(5)
    )).scalars().all()

    productivity_score = 0
    if total_tasks > 0:
        productivity_score = int((completed_tasks / total_tasks) * 100)

    return {
        "tasks": {
            "today": tasks_today,
            "completed_today": tasks_completed_today,
            "total": total_tasks,
            "completed": completed_tasks,
        },
        "notes": {"total": total_notes},
        "research": {"publications": total_publications},
        "projects": {"active": active_projects},
        "finance": {"monthly_expense": float(monthly_expense)},
        "habits": {"active": active_habits, "done_today": habits_done_today},
        "productivity_score": productivity_score,
        "recent_tasks": [{"id": t.id, "title": t.title, "due_date": t.due_date, "priority": t.priority} for t in recent_tasks],
        "recent_notes": [{"id": n.id, "title": n.title, "updated_at": n.updated_at} for n in recent_notes],
        "today": str(today),
    }


@router.get("/widgets")
async def get_widgets(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    from app.models.settings import Widget
    widgets = (await db.execute(
        select(Widget).where(Widget.is_visible == True).order_by(Widget.order_index)
    )).scalars().all()
    return {"widgets": widgets}
