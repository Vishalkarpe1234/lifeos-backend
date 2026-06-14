from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.calendar_event import CalendarEvent

router = APIRouter(prefix="/calendar", tags=["Calendar"])


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    all_day: bool = False
    color: str = "#6366F1"
    category: str = "general"
    location: Optional[str] = None


@router.get("")
async def list_events(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CalendarEvent).where(CalendarEvent.user_id == current_user.id).order_by(CalendarEvent.start_time.desc()))
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "start_time": e.start_time.isoformat() if e.start_time else None,
            "end_time": e.end_time.isoformat() if e.end_time else None,
            "all_day": e.all_day,
            "color": e.color,
            "category": e.category,
            "location": e.location,
        }
        for e in events
    ]


@router.post("")
async def create_event(body: EventCreate, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    event = CalendarEvent(user_id=current_user.id, **body.model_dump(exclude_none=True))
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return {"id": event.id, "title": event.title}


@router.delete("/{event_id}")
async def delete_event(event_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.user_id == current_user.id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.delete(event)
    await db.commit()
    return {"ok": True}
