from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.bookmark import Bookmark, BookmarkFolder

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


# ── Folders ────────────────────────────────────────────────────────────────────

@router.get("/folders/")
async def list_folders(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    result = await db.execute(select(BookmarkFolder).order_by(BookmarkFolder.order_index))
    return [_folder_dict(f) for f in result.scalars().all()]


@router.post("/folders/", status_code=status.HTTP_201_CREATED)
async def create_folder(data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    folder = BookmarkFolder(name=data.get("name", ""), color=data.get("color", "#6366F1"), icon=data.get("icon"), order_index=data.get("order_index", 0))
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return _folder_dict(folder)


@router.put("/folders/{folder_id}")
async def update_folder(folder_id: int, data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    result = await db.execute(select(BookmarkFolder).where(BookmarkFolder.id == folder_id))
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    for k, v in data.items():
        if hasattr(folder, k):
            setattr(folder, k, v)
    await db.commit()
    await db.refresh(folder)
    return _folder_dict(folder)


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(folder_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    result = await db.execute(select(BookmarkFolder).where(BookmarkFolder.id == folder_id))
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    await db.delete(folder)
    await db.commit()


# ── Bookmarks ──────────────────────────────────────────────────────────────────

@router.get("/")
async def list_bookmarks(
    folder_id: Optional[int] = None,
    is_favorite: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(Bookmark)
    if folder_id is not None:
        q = q.where(Bookmark.folder_id == folder_id)
    if is_favorite is not None:
        q = q.where(Bookmark.is_favorite == is_favorite)
    if search:
        q = q.where(Bookmark.title.ilike(f"%{search}%") | Bookmark.url.ilike(f"%{search}%"))
    q = q.order_by(Bookmark.is_favorite.desc(), Bookmark.created_at.desc())
    offset = (page - 1) * page_size
    result = await db.execute(q.offset(offset).limit(page_size))
    bookmarks = result.scalars().all()
    total = (await db.execute(select(func.count()).select_from(Bookmark))).scalar_one()
    return {"items": [_bookmark_dict(b) for b in bookmarks], "total": total, "page": page, "page_size": page_size}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_bookmark(data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    bookmark = Bookmark(
        url=data.get("url", ""),
        title=data.get("title", data.get("url", "")),
        description=data.get("description"),
        favicon_url=data.get("favicon_url"),
        thumbnail_url=data.get("thumbnail_url"),
        folder_id=data.get("folder_id"),
        folder_name=data.get("folder_name"),
        is_favorite=data.get("is_favorite", False),
        is_read=data.get("is_read", False),
        tags=data.get("tags", []),
        notes=data.get("notes"),
    )
    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark)
    return _bookmark_dict(bookmark)


@router.get("/{bookmark_id}")
async def get_bookmark(bookmark_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return _bookmark_dict(await _get_or_404(bookmark_id, db))


@router.put("/{bookmark_id}")
async def update_bookmark(bookmark_id: int, data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    bookmark = await _get_or_404(bookmark_id, db)
    updatable = {"title", "url", "description", "folder_id", "folder_name", "is_favorite", "is_read", "tags", "notes"}
    for k, v in data.items():
        if k in updatable:
            setattr(bookmark, k, v)
    await db.commit()
    await db.refresh(bookmark)
    return _bookmark_dict(bookmark)


@router.patch("/{bookmark_id}/favorite")
async def toggle_favorite(bookmark_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    bookmark = await _get_or_404(bookmark_id, db)
    bookmark.is_favorite = not bookmark.is_favorite
    await db.commit()
    return {"id": bookmark.id, "is_favorite": bookmark.is_favorite}


@router.patch("/{bookmark_id}/read")
async def toggle_read(bookmark_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    bookmark = await _get_or_404(bookmark_id, db)
    bookmark.is_read = not bookmark.is_read
    await db.commit()
    return {"id": bookmark.id, "is_read": bookmark.is_read}


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(bookmark_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    bookmark = await _get_or_404(bookmark_id, db)
    await db.delete(bookmark)
    await db.commit()


async def _get_or_404(bookmark_id: int, db: AsyncSession) -> Bookmark:
    result = await db.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
    bookmark = result.scalar_one_or_none()
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return bookmark


def _folder_dict(f: BookmarkFolder) -> dict:
    return {"id": f.id, "name": f.name, "color": f.color, "icon": f.icon, "order_index": f.order_index, "created_at": f.created_at.isoformat() if f.created_at else None}


def _bookmark_dict(b: Bookmark) -> dict:
    return {
        "id": b.id, "url": b.url, "title": b.title, "description": b.description,
        "favicon_url": b.favicon_url, "thumbnail_url": b.thumbnail_url,
        "folder_id": b.folder_id, "folder_name": b.folder_name,
        "is_favorite": b.is_favorite, "is_read": b.is_read, "tags": b.tags, "notes": b.notes,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }
