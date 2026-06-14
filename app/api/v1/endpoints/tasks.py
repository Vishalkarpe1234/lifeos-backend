from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc, and_
from typing import Optional, List
from pydantic import BaseModel
from datetime import date, datetime

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.task import Task, TaskCategory
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    priority: str = "medium"
    status: str = "todo"
    due_date: Optional[date] = None
    due_time: Optional[str] = None
    tags: List[str] = []
    sub_tasks: List[dict] = []
    repeat: Optional[str] = None
    module: Optional[str] = None
    is_pinned: bool = False
    notes: Optional[str] = None
    reminder_at: Optional[datetime] = None


class TaskUpdate(TaskCreate):
    title: Optional[str] = None
    is_completed: Optional[bool] = None


class CategoryCreate(BaseModel):
    name: str
    color: str = "#6366F1"
    icon: Optional[str] = None
    order_index: int = 0


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    items = (await db.execute(select(TaskCategory).order_by(TaskCategory.order_index))).scalars().all()
    return {"items": items}


@router.post("/categories", status_code=201)
async def create_category(data: CategoryCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    cat = TaskCategory(**data.model_dump())
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


@router.delete("/categories/{cat_id}", response_model=SuccessResponse)
async def delete_category(cat_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    cat = (await db.execute(select(TaskCategory).where(TaskCategory.id == cat_id))).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    await db.delete(cat)
    return SuccessResponse(message="Category deleted")


@router.get("/")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category_id: Optional[int] = None,
    module: Optional[str] = None,
    due_date: Optional[date] = None,
    is_completed: Optional[bool] = None,
    search: Optional[str] = None,
    is_pinned: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    filters = []
    if status:
        filters.append(Task.status == status)
    if priority:
        filters.append(Task.priority == priority)
    if category_id:
        filters.append(Task.category_id == category_id)
    if module:
        filters.append(Task.module == module)
    if due_date:
        filters.append(Task.due_date == due_date)
    if is_completed is not None:
        filters.append(Task.is_completed == is_completed)
    if is_pinned is not None:
        filters.append(Task.is_pinned == is_pinned)
    if search:
        filters.append(or_(Task.title.ilike(f"%{search}%"), Task.description.ilike(f"%{search}%")))

    query = select(Task)
    count_q = select(func.count()).select_from(Task)
    if filters:
        query = query.where(and_(*filters))
        count_q = count_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar()
    skip = (page - 1) * page_size
    items = (await db.execute(
        query.order_by(Task.is_pinned.desc(), Task.due_date.asc().nullslast(), desc(Task.created_at))
        .offset(skip).limit(page_size)
    )).scalars().all()

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/", status_code=201)
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    task = Task(**data.model_dump())
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@router.put("/{task_id}")
async def update_task(task_id: int, data: TaskUpdate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    if data.is_completed:
        task.completed_at = datetime.now()
    await db.flush()
    await db.refresh(task)
    return task


@router.patch("/{task_id}/complete", response_model=SuccessResponse)
async def toggle_complete(task_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.is_completed = not task.is_completed
    task.completed_at = datetime.now() if task.is_completed else None
    task.status = "done" if task.is_completed else "todo"
    await db.flush()
    return SuccessResponse(message=f"Task marked as {'complete' if task.is_completed else 'incomplete'}")


@router.delete("/{task_id}", response_model=SuccessResponse)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    return SuccessResponse(message="Task deleted")


@router.get("/stats/summary")
async def task_stats(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    total = (await db.execute(select(func.count()).select_from(Task))).scalar()
    completed = (await db.execute(select(func.count()).select_from(Task).where(Task.is_completed == True))).scalar()
    pending = (await db.execute(select(func.count()).select_from(Task).where(Task.is_completed == False))).scalar()
    overdue = (await db.execute(
        select(func.count()).select_from(Task).where(
            and_(Task.due_date < date.today(), Task.is_completed == False)
        )
    )).scalar()
    return {"total": total, "completed": completed, "pending": pending, "overdue": overdue}
