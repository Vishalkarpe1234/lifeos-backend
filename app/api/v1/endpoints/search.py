from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.note import Note
from app.models.task import Task
from app.models.journal import JournalEntry
from app.models.goal import Goal
from app.models.contact import Contact

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("")
async def search(q: str = "", current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not q or len(q) < 2:
        return []

    results = []
    uid = current_user.id

    notes = (await db.execute(select(Note).where(Note.user_id == uid, or_(Note.title.ilike(f"%{q}%"), Note.content.ilike(f"%{q}%"))).limit(5))).scalars().all()
    for n in notes:
        results.append({"type": "note", "id": n.id, "title": n.title, "preview": (n.content or '')[:80]})

    tasks = (await db.execute(select(Task).where(Task.user_id == uid, Task.title.ilike(f"%{q}%")).limit(5))).scalars().all()
    for t in tasks:
        results.append({"type": "task", "id": t.id, "title": t.title, "preview": t.status})

    goals = (await db.execute(select(Goal).where(Goal.user_id == uid, or_(Goal.title.ilike(f"%{q}%"), Goal.description.ilike(f"%{q}%"))).limit(5))).scalars().all()
    for g in goals:
        results.append({"type": "goal", "id": g.id, "title": g.title, "preview": g.category})

    try:
        contacts = (await db.execute(select(Contact).where(Contact.user_id == uid, or_(Contact.full_name.ilike(f"%{q}%"), Contact.email.ilike(f"%{q}%"))).limit(5))).scalars().all()
        for c in contacts:
            results.append({"type": "contact", "id": c.id, "title": c.full_name, "preview": c.email or c.phone or ''})
    except Exception:
        pass

    return results
