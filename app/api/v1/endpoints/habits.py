from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from typing import Optional, List
from pydantic import BaseModel
from datetime import date, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.habit import Habit, HabitLog
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/habits", tags=["Habits"])


class HabitCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: str = "#6366F1"
    category: Optional[str] = None
    frequency: str = "daily"
    frequency_days: List[int] = []
    target_count: int = 1
    unit: Optional[str] = None
    reminder_time: Optional[str] = None
    start_date: Optional[date] = None
    order_index: int = 0


class HabitLogCreate(BaseModel):
    habit_id: int
    date: date
    count: int = 1
    value: Optional[float] = None
    notes: Optional[str] = None
    mood: Optional[str] = None


@router.get("/")
async def list_habits(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    items = (await db.execute(
        select(Habit).where(Habit.is_active == True).order_by(Habit.order_index)
    )).scalars().all()
    return {"items": items}


@router.post("/", status_code=201)
async def create_habit(data: HabitCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    habit = Habit(**data.model_dump())
    db.add(habit)
    await db.flush()
    await db.refresh(habit)
    return habit


@router.put("/{habit_id}")
async def update_habit(habit_id: int, data: HabitCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    h = (await db.execute(select(Habit).where(Habit.id == habit_id))).scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Habit not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(h, k, v)
    await db.flush()
    await db.refresh(h)
    return h


@router.delete("/{habit_id}", response_model=SuccessResponse)
async def delete_habit(habit_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    h = (await db.execute(select(Habit).where(Habit.id == habit_id))).scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Habit not found")
    await db.delete(h)
    return SuccessResponse(message="Habit deleted")


@router.get("/logs")
async def list_logs(
    habit_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    filters = []
    if habit_id:
        filters.append(HabitLog.habit_id == habit_id)
    if start_date:
        filters.append(HabitLog.date >= start_date)
    if end_date:
        filters.append(HabitLog.date <= end_date)

    query = select(HabitLog)
    if filters:
        query = query.where(and_(*filters))
    items = (await db.execute(query.order_by(desc(HabitLog.date)))).scalars().all()
    return {"items": items}


@router.post("/logs", status_code=201)
async def log_habit(data: HabitLogCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    existing = (await db.execute(
        select(HabitLog).where(and_(HabitLog.habit_id == data.habit_id, HabitLog.date == data.date))
    )).scalar_one_or_none()

    if existing:
        existing.count = data.count
        existing.value = data.value
        existing.notes = data.notes
        existing.mood = data.mood
        log = existing
    else:
        log = HabitLog(**data.model_dump())
        db.add(log)

    habit = (await db.execute(select(Habit).where(Habit.id == data.habit_id))).scalar_one_or_none()
    if habit and data.is_completed if hasattr(data, 'is_completed') else True:
        await _update_streak(habit, data.date, db)

    await db.flush()
    if not existing:
        await db.refresh(log)
    return log


async def _update_streak(habit: Habit, log_date: date, db: AsyncSession):
    yesterday = log_date - timedelta(days=1)
    yesterday_log = (await db.execute(
        select(HabitLog).where(and_(HabitLog.habit_id == habit.id, HabitLog.date == yesterday, HabitLog.is_completed == True))
    )).scalar_one_or_none()

    if yesterday_log:
        habit.streak_current = (habit.streak_current or 0) + 1
    else:
        habit.streak_current = 1

    if habit.streak_current > (habit.streak_longest or 0):
        habit.streak_longest = habit.streak_current


@router.delete("/logs/{log_id}", response_model=SuccessResponse)
async def delete_log(log_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    log = (await db.execute(select(HabitLog).where(HabitLog.id == log_id))).scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    await db.delete(log)
    return SuccessResponse(message="Log deleted")


@router.get("/today")
async def today_habits(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    today = date.today()
    habits = (await db.execute(select(Habit).where(Habit.is_active == True).order_by(Habit.order_index))).scalars().all()
    logs = (await db.execute(select(HabitLog).where(HabitLog.date == today))).scalars().all()
    log_map = {l.habit_id: l for l in logs}

    result = []
    for h in habits:
        log = log_map.get(h.id)
        result.append({
            "habit": h,
            "logged": log is not None,
            "log": log,
            "completed": log.is_completed if log else False,
        })
    return {"habits": result, "date": str(today)}
