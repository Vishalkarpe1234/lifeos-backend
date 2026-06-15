from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.user import User
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/location", tags=["Location"])


class LocationUpdate(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    timestamp: Optional[str] = None


class PermissionUpdate(BaseModel):
    granted: bool


@router.post("", response_model=SuccessResponse)
async def submit_location(
    data: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if data.timestamp:
        try:
            ts = datetime.fromisoformat(data.timestamp)
        except ValueError:
            ts = datetime.now(timezone.utc)
    else:
        ts = datetime.now(timezone.utc)
    await db.execute(text("""
        INSERT INTO user_locations (user_id, latitude, longitude, accuracy, timestamp)
        VALUES (:uid, :lat, :lng, :acc, :ts)
    """), {"uid": current_user.id, "lat": data.latitude, "lng": data.longitude, "acc": data.accuracy, "ts": ts})
    # Keep only last 50 entries per user
    await db.execute(text("""
        DELETE FROM user_locations WHERE user_id = :uid AND id NOT IN (
            SELECT id FROM user_locations WHERE user_id = :uid ORDER BY id DESC LIMIT 50
        )
    """), {"uid": current_user.id})
    return SuccessResponse(message="Location recorded")


@router.patch("/permission", response_model=SuccessResponse)
async def update_location_permission(
    data: PermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await db.execute(text("UPDATE users SET location_permission = :val WHERE id = :uid"), {"val": data.granted, "uid": current_user.id})
    return SuccessResponse(message="Permission updated")
