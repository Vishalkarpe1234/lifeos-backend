from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from datetime import date

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.journal import JournalEntry

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("/")
async def list_entries(
    page: int = 1,
    page_size: int = 20,
    month: int | None = None,
    year: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(JournalEntry)
    if month:
        q = q.where(extract("month", JournalEntry.date) == month)
    if year:
        q = q.where(extract("year", JournalEntry.date) == year)
    q = q.order_by(JournalEntry.date.desc())
    offset = (page - 1) * page_size
    result = await db.execute(q.offset(offset).limit(page_size))
    entries = result.scalars().all()
    total = (await db.execute(select(func.count()).select_from(JournalEntry))).scalar_one()
    return {"items": [_entry_dict(e) for e in entries], "total": total, "page": page, "page_size": page_size}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_entry(data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    entry_date = date.fromisoformat(data["date"]) if data.get("date") else date.today()
    entry = JournalEntry(
        title=data.get("title"),
        content=data.get("content", ""),
        date=entry_date,
        mood=data.get("mood"),
        mood_score=data.get("mood_score"),
        energy_level=data.get("energy_level"),
        gratitude=data.get("gratitude", []),
        tags=data.get("tags", []),
        weather=data.get("weather"),
        location=data.get("location"),
        is_private=data.get("is_private", True),
        images=data.get("images", []),
        goals_tomorrow=data.get("goals_tomorrow", []),
        highlights=data.get("highlights", []),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _entry_dict(entry)


@router.get("/today")
async def get_today(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    result = await db.execute(select(JournalEntry).where(JournalEntry.date == date.today()).order_by(JournalEntry.created_at.desc()))
    entry = result.scalars().first()
    return _entry_dict(entry) if entry else None


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    from datetime import datetime
    total = (await db.execute(select(func.count()).select_from(JournalEntry))).scalar_one()
    this_year = (await db.execute(select(func.count()).select_from(JournalEntry).where(extract("year", JournalEntry.date) == datetime.now().year))).scalar_one()
    return {"total_entries": total, "entries_this_year": this_year}


@router.get("/{entry_id}")
async def get_entry(entry_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return _entry_dict(await _get_or_404(entry_id, db))


@router.put("/{entry_id}")
async def update_entry(entry_id: int, data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    entry = await _get_or_404(entry_id, db)
    updatable = {"title", "content", "mood", "mood_score", "energy_level", "gratitude", "tags", "is_private", "weather", "location", "images", "goals_tomorrow", "highlights"}
    for k, v in data.items():
        if k in updatable:
            setattr(entry, k, v)
    await db.commit()
    await db.refresh(entry)
    return _entry_dict(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    entry = await _get_or_404(entry_id, db)
    await db.delete(entry)
    await db.commit()


async def _get_or_404(entry_id: int, db: AsyncSession) -> JournalEntry:
    result = await db.execute(select(JournalEntry).where(JournalEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


def _entry_dict(e: JournalEntry) -> dict:
    return {
        "id": e.id, "title": e.title, "content": e.content,
        "date": e.date.isoformat() if e.date else None,
        "mood": e.mood, "mood_score": e.mood_score, "energy_level": e.energy_level,
        "gratitude": e.gratitude, "tags": e.tags, "is_private": e.is_private,
        "weather": e.weather, "location": e.location,
        "images": e.images, "goals_tomorrow": e.goals_tomorrow, "highlights": e.highlights,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }
