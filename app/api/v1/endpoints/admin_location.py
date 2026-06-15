from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.dependencies import get_current_admin

router = APIRouter(prefix="/admin", tags=["Admin Location"])


@router.get("/users/{user_id}/locations")
async def get_user_locations(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    result = await db.execute(text("""
        SELECT latitude, longitude, accuracy, timestamp, created_at
        FROM user_locations
        WHERE user_id = :uid
        ORDER BY id DESC
        LIMIT 20
    """), {"uid": user_id})
    rows = result.fetchall()
    return {"items": [{"latitude": r[0], "longitude": r[1], "accuracy": r[2], "timestamp": str(r[3]), "created_at": str(r[4])} for r in rows]}
