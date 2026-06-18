from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.user import User
from app.models.location_history import LocationHistory
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

    # Also save to history (unlimited retention)
    recorded_at = ts.replace(tzinfo=None) if ts.tzinfo else ts
    history_entry = LocationHistory(
        user_id=current_user.id,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy=data.accuracy,
        recorded_at=recorded_at,
    )
    db.add(history_entry)
    await db.commit()

    return SuccessResponse(message="Location recorded")


@router.patch("/permission", response_model=SuccessResponse)
async def update_location_permission(
    data: PermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await db.execute(text("UPDATE users SET location_permission = :val WHERE id = :uid"), {"val": data.granted, "uid": current_user.id})
    await db.commit()
    return SuccessResponse(message="Permission updated")


@router.get("/history")
async def get_location_history(
    start: Optional[str] = None,
    end: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(LocationHistory).where(LocationHistory.user_id == current_user.id)
    if start:
        try:
            q = q.where(LocationHistory.recorded_at >= datetime.fromisoformat(start.replace("Z", "+00:00")).replace(tzinfo=None))
        except Exception:
            pass
    if end:
        try:
            q = q.where(LocationHistory.recorded_at <= datetime.fromisoformat(end.replace("Z", "+00:00")).replace(tzinfo=None))
        except Exception:
            pass
    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0
    items = (
        await db.execute(
            q.order_by(LocationHistory.recorded_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": h.id,
                "latitude": h.latitude,
                "longitude": h.longitude,
                "accuracy": h.accuracy,
                "recorded_at": h.recorded_at.isoformat(),
            }
            for h in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/history/at")
async def get_location_at_time(
    timestamp: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        ts_naive = ts.replace(tzinfo=None)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timestamp format")

    before = (
        await db.execute(
            select(LocationHistory)
            .where(LocationHistory.user_id == current_user.id)
            .where(LocationHistory.recorded_at <= ts_naive)
            .order_by(LocationHistory.recorded_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    after = (
        await db.execute(
            select(LocationHistory)
            .where(LocationHistory.user_id == current_user.id)
            .where(LocationHistory.recorded_at > ts_naive)
            .order_by(LocationHistory.recorded_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()

    result = None
    if before and after:
        diff_before = abs((ts_naive - before.recorded_at.replace(tzinfo=None)).total_seconds())
        diff_after = abs((after.recorded_at.replace(tzinfo=None) - ts_naive).total_seconds())
        result = before if diff_before <= diff_after else after
    else:
        result = before or after

    if not result:
        raise HTTPException(status_code=404, detail="No location data found")

    return {
        "latitude": result.latitude,
        "longitude": result.longitude,
        "accuracy": result.accuracy,
        "recorded_at": result.recorded_at.isoformat(),
    }
