from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from typing import Optional
from pathlib import Path

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.media import MediaFile
from app.schemas.common import SuccessResponse
from app.services.storage_service import storage_service

router = APIRouter(prefix="/media", tags=["Media"])


@router.get("/")
async def list_media(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    file_type: Optional[str] = None,
    category: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    filters = []
    if file_type:
        filters.append(MediaFile.file_type == file_type)
    if category:
        filters.append(MediaFile.category == category)
    if module:
        filters.append(MediaFile.module == module)
    if search:
        filters.append(or_(
            MediaFile.original_filename.ilike(f"%{search}%"),
            MediaFile.description.ilike(f"%{search}%"),
        ))

    query = select(MediaFile)
    count_q = select(func.count()).select_from(MediaFile)
    if filters:
        query = query.where(and_(*filters))
        count_q = count_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar()
    skip = (page - 1) * page_size
    items = (await db.execute(query.order_by(desc(MediaFile.created_at)).offset(skip).limit(page_size))).scalars().all()
    return {"items": items, "total": total, "page": page}


@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    category: Optional[str] = "general",
    module: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    subfolder = f"{module or 'uploads'}/{category or 'general'}"
    result = await storage_service.upload_file(file, subfolder=subfolder)

    media = MediaFile(
        filename=result["filename"],
        original_filename=result["original_filename"],
        file_path=result["file_path"],
        file_url=result["file_url"],
        file_type=result["file_type"],
        mime_type=result["mime_type"],
        file_size=result["file_size"],
        category=category,
        module=module,
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)
    return media


@router.delete("/{media_id}", response_model=SuccessResponse)
async def delete_media(media_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    media = (await db.execute(select(MediaFile).where(MediaFile.id == media_id))).scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="File not found")
    await storage_service.delete_file(media.file_path)
    await db.delete(media)
    return SuccessResponse(message="File deleted")


@router.get("/storage/stats")
async def storage_stats(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    total_files = (await db.execute(select(func.count()).select_from(MediaFile))).scalar()
    total_size = (await db.execute(select(func.sum(MediaFile.file_size)))).scalar() or 0
    by_type = (await db.execute(
        select(MediaFile.file_type, func.count().label("count"), func.sum(MediaFile.file_size).label("size"))
        .group_by(MediaFile.file_type)
    )).all()
    return {
        "total_files": total_files,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "by_type": [{"type": r[0], "count": r[1], "size_bytes": r[2] or 0} for r in by_type],
    }
