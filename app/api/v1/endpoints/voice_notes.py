from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.voice_note import VoiceNote

router = APIRouter(prefix="/voice-notes", tags=["Voice Notes"])


class VoiceNoteCreate(BaseModel):
    title: str = "Voice Note"
    transcript: Optional[str] = None
    duration: int = 0


@router.get("")
async def list_notes(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VoiceNote).where(VoiceNote.user_id == current_user.id).order_by(VoiceNote.created_at.desc()))
    notes = result.scalars().all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "duration": n.duration,
            "transcript": n.transcript,
            "ai_summary": n.ai_summary,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notes
    ]


@router.post("")
async def create_note(body: VoiceNoteCreate, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    note = VoiceNote(user_id=current_user.id, **body.model_dump(exclude_none=True))
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return {"id": note.id, "title": note.title}


@router.delete("/{note_id}")
async def delete_note(note_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VoiceNote).where(VoiceNote.id == note_id, VoiceNote.user_id == current_user.id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Voice note not found")
    await db.delete(note)
    await db.commit()
    return {"ok": True}
