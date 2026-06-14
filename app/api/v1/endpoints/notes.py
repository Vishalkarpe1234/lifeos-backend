from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc, and_
from typing import Optional, List
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.note import Note, NoteTag
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/notes", tags=["Notes"])


class NoteCreate(BaseModel):
    title: str
    content: Optional[str] = None
    content_type: str = "markdown"
    category: Optional[str] = None
    tags: List[str] = []
    is_pinned: bool = False
    color: Optional[str] = None
    module: Optional[str] = None


class NoteUpdate(NoteCreate):
    title: Optional[str] = None


@router.get("/")
async def list_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_pinned: Optional[bool] = None,
    is_archived: Optional[bool] = False,
    module: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    filters = [Note.is_archived == is_archived]
    if search:
        filters.append(or_(Note.title.ilike(f"%{search}%"), Note.content.ilike(f"%{search}%")))
    if category:
        filters.append(Note.category == category)
    if is_pinned is not None:
        filters.append(Note.is_pinned == is_pinned)
    if module:
        filters.append(Note.module == module)

    query = select(Note).where(and_(*filters))
    count_q = select(func.count()).select_from(Note).where(and_(*filters))
    total = (await db.execute(count_q)).scalar()
    skip = (page - 1) * page_size
    items = (await db.execute(query.order_by(Note.is_pinned.desc(), desc(Note.updated_at)).offset(skip).limit(page_size))).scalars().all()
    return {"items": items, "total": total, "page": page}


@router.get("/{note_id}")
async def get_note(note_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    note = (await db.execute(select(Note).where(Note.id == note_id))).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.post("/", status_code=201)
async def create_note(data: NoteCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    note = Note(**data.model_dump())
    if note.content:
        note.word_count = len(note.content.split())
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return note


@router.put("/{note_id}")
async def update_note(note_id: int, data: NoteUpdate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    note = (await db.execute(select(Note).where(Note.id == note_id))).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(note, k, v)
    if note.content:
        note.word_count = len(note.content.split())
    await db.flush()
    await db.refresh(note)
    return note


@router.patch("/{note_id}/pin", response_model=SuccessResponse)
async def toggle_pin(note_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    note = (await db.execute(select(Note).where(Note.id == note_id))).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    note.is_pinned = not note.is_pinned
    await db.flush()
    return SuccessResponse(message="Note pin toggled")


@router.patch("/{note_id}/archive", response_model=SuccessResponse)
async def toggle_archive(note_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    note = (await db.execute(select(Note).where(Note.id == note_id))).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    note.is_archived = not note.is_archived
    await db.flush()
    return SuccessResponse(message="Note archive toggled")


@router.delete("/{note_id}", response_model=SuccessResponse)
async def delete_note(note_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    note = (await db.execute(select(Note).where(Note.id == note_id))).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    return SuccessResponse(message="Note deleted")
