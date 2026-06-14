from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import date, datetime, timezone
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.health_entry import HealthEntry

router = APIRouter(prefix="/health", tags=["Health"])


class HealthLog(BaseModel):
    date: Optional[date] = None
    weight: Optional[float] = None
    water_ml: Optional[int] = None
    sleep_hours: Optional[float] = None
    steps: Optional[int] = None
    calories: Optional[int] = None
    heart_rate: Optional[int] = None
    mood: Optional[int] = None
    workout_minutes: Optional[int] = None
    notes: Optional[str] = None


@router.get("/today")
async def get_today(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    today = date.today()
    result = await db.execute(select(HealthEntry).where(HealthEntry.user_id == current_user.id, HealthEntry.date == today))
    entry = result.scalar_one_or_none()
    if not entry:
        return {}
    return {
        "date": entry.date.isoformat(),
        "weight": entry.weight,
        "water_ml": entry.water_ml,
        "sleep_hours": entry.sleep_hours,
        "steps": entry.steps,
        "calories": entry.calories,
        "heart_rate": entry.heart_rate,
        "mood": entry.mood,
        "workout_minutes": entry.workout_minutes,
        "notes": entry.notes,
    }


@router.post("")
async def log_health(body: HealthLog, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    log_date = body.date or date.today()
    result = await db.execute(select(HealthEntry).where(HealthEntry.user_id == current_user.id, HealthEntry.date == log_date))
    entry = result.scalar_one_or_none()
    if entry:
        for k, v in body.model_dump(exclude_none=True).items():
            if k != 'date':
                setattr(entry, k, v)
    else:
        data = body.model_dump(exclude_none=True)
        data['date'] = log_date
        entry = HealthEntry(user_id=current_user.id, **data)
        db.add(entry)
    await db.commit()
    return {"ok": True}


@router.get("")
async def list_health(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(HealthEntry).where(HealthEntry.user_id == current_user.id).order_by(HealthEntry.date.desc()).limit(30))
    entries = result.scalars().all()
    return [{"date": e.date.isoformat(), "water_ml": e.water_ml, "sleep_hours": e.sleep_hours, "steps": e.steps, "mood": e.mood} for e in entries]
