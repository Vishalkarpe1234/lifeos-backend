from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from pydantic import BaseModel
from typing import Optional, List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.snippet import CodeSnippet
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/snippets", tags=["Snippets"])


class SnippetCreate(BaseModel):
    title: str
    language: str = "python"
    code: str
    description: Optional[str] = None
    tags: List[str] = []
    is_favorite: bool = False


class SnippetUpdate(BaseModel):
    title: Optional[str] = None
    language: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    is_favorite: Optional[bool] = None


@router.get("/")
async def list_snippets(
    search: Optional[str] = None,
    language: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(CodeSnippet)
    if search:
        q = q.where(
            or_(
                CodeSnippet.title.ilike(f"%{search}%"),
                CodeSnippet.description.ilike(f"%{search}%"),
            )
        )
    if language:
        q = q.where(CodeSnippet.language == language)
    total = (
        await db.execute(select(func.count()).select_from(CodeSnippet))
    ).scalar()
    items = (
        await db.execute(
            q.order_by(
                CodeSnippet.is_favorite.desc(), CodeSnippet.created_at.desc()
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": s.id,
                "title": s.title,
                "language": s.language,
                "code": s.code,
                "description": s.description,
                "tags": s.tags,
                "is_favorite": s.is_favorite,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in items
        ],
        "total": total,
    }


@router.post("/", status_code=201)
async def create_snippet(
    data: SnippetCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    s = CodeSnippet(**data.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"id": s.id, "title": s.title}


@router.put("/{sid}")
async def update_snippet(
    sid: int,
    data: SnippetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    s = (
        await db.execute(select(CodeSnippet).where(CodeSnippet.id == sid))
    ).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    await db.commit()
    return {"ok": True}


@router.delete("/{sid}", response_model=SuccessResponse)
async def delete_snippet(
    sid: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    s = (
        await db.execute(select(CodeSnippet).where(CodeSnippet.id == sid))
    ).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Not found")
    await db.delete(s)
    await db.commit()
    return SuccessResponse(message="Deleted")
