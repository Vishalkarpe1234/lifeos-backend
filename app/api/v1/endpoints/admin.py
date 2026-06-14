from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from pydantic import BaseModel
from typing import Optional, Any
import json

from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.core.security import get_password_hash
from app.models.settings import AppSettings, Widget
from app.models.analytics import ActivityLog
from app.models.user import User
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


class SettingUpsert(BaseModel):
    key: str
    value: Optional[str] = None
    value_json: Optional[Any] = None
    category: str = "general"
    description: Optional[str] = None
    is_public: bool = False


class WidgetCreate(BaseModel):
    widget_type: str
    title: Optional[str] = None
    config: dict = {}
    position: dict = {}
    is_visible: bool = True
    order_index: int = 0
    dashboard_section: str = "main"


class UserCreate(BaseModel):
    email: str
    password: str
    is_admin: bool = False


@router.get("/settings")
async def get_all_settings(db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    items = (await db.execute(select(AppSettings).order_by(AppSettings.category, AppSettings.key))).scalars().all()
    return {"items": items}


@router.post("/settings", status_code=201)
async def upsert_setting(data: SettingUpsert, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    existing = (await db.execute(select(AppSettings).where(AppSettings.key == data.key))).scalar_one_or_none()
    if existing:
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(existing, k, v)
        setting = existing
    else:
        setting = AppSettings(**data.model_dump())
        db.add(setting)
    await db.flush()
    await db.refresh(setting)
    return setting


@router.delete("/settings/{setting_id}", response_model=SuccessResponse)
async def delete_setting(setting_id: int, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    s = (await db.execute(select(AppSettings).where(AppSettings.id == setting_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Setting not found")
    await db.delete(s)
    return SuccessResponse(message="Setting deleted")


@router.get("/widgets")
async def list_widgets(db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    items = (await db.execute(select(Widget).order_by(Widget.order_index))).scalars().all()
    return {"items": items}


@router.post("/widgets", status_code=201)
async def create_widget(data: WidgetCreate, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    widget = Widget(**data.model_dump())
    db.add(widget)
    await db.flush()
    await db.refresh(widget)
    return widget


@router.put("/widgets/{widget_id}")
async def update_widget(widget_id: int, data: WidgetCreate, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    w = (await db.execute(select(Widget).where(Widget.id == widget_id))).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(w, k, v)
    await db.flush()
    await db.refresh(w)
    return w


@router.delete("/widgets/{widget_id}", response_model=SuccessResponse)
async def delete_widget(widget_id: int, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    w = (await db.execute(select(Widget).where(Widget.id == widget_id))).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    await db.delete(w)
    return SuccessResponse(message="Widget deleted")


@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    users = (await db.execute(select(User))).scalars().all()
    return {"items": [{"id": u.id, "email": u.email, "is_admin": u.is_admin, "is_active": u.is_active, "last_login": u.last_login} for u in users]}


@router.post("/users", status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    existing = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=data.email, hashed_password=get_password_hash(data.password), is_admin=data.is_admin)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return {"id": user.id, "email": user.email, "is_admin": user.is_admin}


@router.patch("/users/{user_id}/toggle-active", response_model=SuccessResponse)
async def toggle_user_active(user_id: int, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user.is_active = not user.is_active
    await db.flush()
    return SuccessResponse(message=f"User {'activated' if user.is_active else 'deactivated'}")


@router.delete("/users/{user_id}", response_model=SuccessResponse)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    await db.delete(user)
    return SuccessResponse(message="User deleted")


@router.get("/all-notes")
async def get_all_notes(db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    from app.models.note import Note
    from sqlalchemy import select, desc
    notes = (await db.execute(
        select(Note, User).join(User, Note.user_id == User.id, isouter=True)
        .order_by(desc(Note.created_at)).limit(200)
    )).all()
    return {"items": [{"id": n.id, "title": n.title, "content": n.content,
                       "user_email": u.email if u else "unknown",
                       "created_at": str(n.created_at), "is_pinned": n.is_pinned}
                      for n, u in notes]}


@router.get("/logs")
async def get_activity_logs(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    total = (await db.execute(select(func.count()).select_from(ActivityLog))).scalar()
    skip = (page - 1) * page_size
    items = (await db.execute(select(ActivityLog).order_by(ActivityLog.created_at.desc()).offset(skip).limit(page_size))).scalars().all()
    return {"items": items, "total": total}


@router.get("/analytics/overview")
async def get_analytics_overview(db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    from app.models.task import Task
    from app.models.note import Note
    from app.models.research import ResearchPublication
    from app.models.project import Project
    from app.models.certificate import Certificate
    from app.models.media import MediaFile

    return {
        "tasks": (await db.execute(select(func.count()).select_from(Task))).scalar(),
        "notes": (await db.execute(select(func.count()).select_from(Note))).scalar(),
        "publications": (await db.execute(select(func.count()).select_from(ResearchPublication))).scalar(),
        "projects": (await db.execute(select(func.count()).select_from(Project))).scalar(),
        "certificates": (await db.execute(select(func.count()).select_from(Certificate))).scalar(),
        "media_files": (await db.execute(select(func.count()).select_from(MediaFile))).scalar(),
        "users": (await db.execute(select(func.count()).select_from(User))).scalar(),
    }
