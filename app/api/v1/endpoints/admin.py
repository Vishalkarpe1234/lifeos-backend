from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from pydantic import BaseModel
from typing import Optional, Any, List
import json

from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.core.security import get_password_hash
from app.models.settings import AppSettings, Widget
from app.models.analytics import ActivityLog
from app.models.user import User
from app.models.note import Note
from app.models.profile import Profile
from app.schemas.common import SuccessResponse
from sqlalchemy import desc

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
    from sqlalchemy import func
    users = (await db.execute(select(User))).scalars().all()
    result = []
    for u in users:
        note_count = (await db.execute(select(func.count()).select_from(Note).where(Note.user_id == u.id))).scalar()
        result.append({
            "id": u.id, "email": u.email, "is_admin": u.is_admin,
            "is_active": u.is_active, "last_login": str(u.last_login) if u.last_login else None,
            "created_at": str(u.created_at), "note_count": note_count or 0,
            "location_permission": getattr(u, 'location_permission', False) or False,
        })
    return {"items": result}


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


class BulkDeleteRequest(BaseModel):
    user_ids: List[int]

@router.post("/users/bulk-delete", response_model=SuccessResponse)
async def bulk_delete_users(data: BulkDeleteRequest, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    for uid in data.user_ids:
        if uid == admin.id:
            continue
        user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if user:
            await db.delete(user)
    return SuccessResponse(message=f"Deleted {len(data.user_ids)} users")


@router.get("/users/{user_id}/notes")
async def get_user_notes(user_id: int, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    notes = (await db.execute(select(Note).where(Note.user_id == user_id).order_by(desc(Note.created_at)))).scalars().all()
    return {"items": [{"id": n.id, "title": n.title, "content": n.content, "is_pinned": n.is_pinned, "created_at": str(n.created_at), "updated_at": str(n.updated_at)} for n in notes]}


class UserEdit(BaseModel):
    email: Optional[str] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = None

@router.patch("/users/{user_id}", response_model=SuccessResponse)
async def edit_user(user_id: int, data: UserEdit, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.email:
        user.email = data.email.lower().strip()
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.full_name:
        profile = (await db.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one_or_none()
        if profile:
            profile.full_name = data.full_name
        else:
            db.add(Profile(user_id=user_id, full_name=data.full_name))
    await db.flush()
    return SuccessResponse(message="User updated")


class AdminPasswordChange(BaseModel):
    current_password: str
    new_password: str

@router.patch("/profile/password", response_model=SuccessResponse)
async def admin_change_password(data: AdminPasswordChange, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    from app.core.security import verify_password, get_password_hash
    if not verify_password(data.current_password, admin.hashed_password):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    admin.hashed_password = get_password_hash(data.new_password)
    await db.flush()
    return SuccessResponse(message="Password changed")


class AdminEmailChange(BaseModel):
    new_email: str
    current_password: str

@router.patch("/profile/email", response_model=SuccessResponse)
async def admin_change_email(data: AdminEmailChange, db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
    from app.core.security import verify_password
    if not verify_password(data.current_password, admin.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    admin.email = data.new_email.lower().strip()
    await db.flush()
    return SuccessResponse(message="Email changed")


@router.get("/all-notes")
async def get_all_notes(db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)):
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
