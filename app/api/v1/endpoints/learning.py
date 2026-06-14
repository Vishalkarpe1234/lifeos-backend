from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.learning_item import LearningItem

router = APIRouter(prefix="/learning", tags=["Learning"])


class LearningCreate(BaseModel):
    title: str
    resource_type: str = "book"
    url: Optional[str] = None
    author: Optional[str] = None
    status: str = "wishlist"


class LearningUpdate(BaseModel):
    status: Optional[str] = None
    progress: Optional[int] = None
    rating: Optional[int] = None
    notes: Optional[str] = None


@router.get("")
async def list_items(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LearningItem).where(LearningItem.user_id == current_user.id).order_by(LearningItem.created_at.desc()))
    items = result.scalars().all()
    return [
        {
            "id": i.id,
            "title": i.title,
            "resource_type": i.resource_type,
            "url": i.url,
            "author": i.author,
            "status": i.status,
            "progress": i.progress,
            "rating": i.rating,
        }
        for i in items
    ]


@router.post("")
async def create_item(body: LearningCreate, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = LearningItem(user_id=current_user.id, **body.model_dump(exclude_none=True))
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": item.id, "title": item.title}


@router.patch("/{item_id}")
async def update_item(item_id: int, body: LearningUpdate, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LearningItem).where(LearningItem.id == item_id, LearningItem.user_id == current_user.id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(item, k, v)
    await db.commit()
    return {"ok": True}


@router.delete("/{item_id}")
async def delete_item(item_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LearningItem).where(LearningItem.id == item_id, LearningItem.user_id == current_user.id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()
    return {"ok": True}
