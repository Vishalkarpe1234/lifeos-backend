from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import date
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.goal import Goal

router = APIRouter(prefix="/goals", tags=["Goals"])


class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str = "personal"
    target_date: Optional[date] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None


@router.get("")
async def list_goals(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Goal).where(Goal.user_id == current_user.id).order_by(Goal.created_at.desc()))
    goals = result.scalars().all()
    return [
        {
            "id": g.id,
            "title": g.title,
            "description": g.description,
            "category": g.category,
            "status": g.status,
            "progress": g.progress,
            "target_date": g.target_date.isoformat() if g.target_date else None,
            "created_at": g.created_at.isoformat() if g.created_at else None,
        }
        for g in goals
    ]


@router.post("")
async def create_goal(body: GoalCreate, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    goal = Goal(user_id=current_user.id, **body.model_dump(exclude_none=True))
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return {"id": goal.id, "title": goal.title, "status": goal.status}


@router.patch("/{goal_id}")
async def update_goal(goal_id: int, body: GoalUpdate, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(goal, k, v)
    await db.commit()
    return {"ok": True}


@router.delete("/{goal_id}")
async def delete_goal(goal_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.delete(goal)
    await db.commit()
    return {"ok": True}
