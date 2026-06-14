from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.timeline_entry import TimelineEntry

router = APIRouter(prefix="/timeline", tags=["Timeline"])


@router.get("")
async def list_timeline(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TimelineEntry)
        .where(TimelineEntry.user_id == current_user.id)
        .order_by(TimelineEntry.entry_date.desc())
        .limit(100)
    )
    items = result.scalars().all()
    return [
        {
            "id": i.id,
            "entry_type": i.entry_type,
            "title": i.title,
            "description": i.description,
            "color": i.color,
            "entry_date": i.entry_date.isoformat() if i.entry_date else None,
        }
        for i in items
    ]
