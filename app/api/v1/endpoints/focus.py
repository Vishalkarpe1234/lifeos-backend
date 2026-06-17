from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from datetime import date
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.focus import FocusSession

router = APIRouter(prefix="/focus", tags=["Focus"])


class SessionCreate(BaseModel):
    duration_minutes: int
    rounds_completed: int = 1
    focus_type: str = "pomodoro"
    date: Optional[date] = None


@router.get("/sessions")
async def list_sessions(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(FocusSession).order_by(
        FocusSession.date.desc(), FocusSession.created_at.desc()
    )
    total = (
        await db.execute(select(func.count()).select_from(FocusSession))
    ).scalar()
    items = (
        await db.execute(q.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return {
        "items": [
            {
                "id": s.id,
                "duration_minutes": s.duration_minutes,
                "rounds_completed": s.rounds_completed,
                "focus_type": s.focus_type,
                "date": s.date.isoformat() if s.date else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in items
        ],
        "total": total,
    }


@router.post("/sessions", status_code=201)
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    session = FocusSession(
        duration_minutes=data.duration_minutes,
        rounds_completed=data.rounds_completed,
        focus_type=data.focus_type,
        date=data.date or date.today(),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"id": session.id, "duration_minutes": session.duration_minutes}


@router.get("/stats")
async def focus_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    total_sessions = (
        await db.execute(select(func.count()).select_from(FocusSession))
    ).scalar()
    total_minutes = (
        await db.execute(
            select(func.sum(FocusSession.duration_minutes)).select_from(FocusSession)
        )
    ).scalar() or 0
    today_minutes = (
        await db.execute(
            select(func.sum(FocusSession.duration_minutes)).where(
                FocusSession.date == date.today()
            )
        )
    ).scalar() or 0
    return {
        "total_sessions": total_sessions,
        "total_minutes": total_minutes,
        "today_minutes": today_minutes,
        "total_hours": round(total_minutes / 60, 1),
    }
