from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from typing import Optional, List
from pydantic import BaseModel
from datetime import date

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.project import Project, ProjectTask
from app.schemas.common import SuccessResponse
from app.services.storage_service import storage_service

router = APIRouter(prefix="/projects", tags=["Projects"])


class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    category: Optional[str] = None
    status: str = "active"
    technologies: List[str] = []
    features: List[str] = []
    architecture: Optional[str] = None
    github_url: Optional[str] = None
    live_url: Optional[str] = None
    documentation_url: Optional[str] = None
    images: List[str] = []
    videos: List[str] = []
    thumbnail_url: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_featured: bool = False
    is_public: bool = True
    version: Optional[str] = None
    tags: List[str] = []
    progress_percent: int = 0
    collaborators: List[str] = []
    order_index: int = 0


class ProjectUpdate(ProjectCreate):
    title: Optional[str] = None


class ProjectTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "todo"
    priority: str = "medium"
    due_date: Optional[date] = None


@router.get("/")
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    is_featured: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    filters = []
    if search:
        filters.append(or_(Project.title.ilike(f"%{search}%"), Project.description.ilike(f"%{search}%")))
    if status:
        filters.append(Project.status == status)
    if category:
        filters.append(Project.category == category)
    if is_featured is not None:
        filters.append(Project.is_featured == is_featured)

    query = select(Project)
    count_q = select(func.count()).select_from(Project)
    if filters:
        query = query.where(and_(*filters))
        count_q = count_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar()
    skip = (page - 1) * page_size
    items = (await db.execute(query.order_by(Project.is_featured.desc(), Project.order_index).offset(skip).limit(page_size))).scalars().all()
    return {"items": items, "total": total, "page": page}


@router.get("/{project_id}")
async def get_project(project_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    tasks = (await db.execute(select(ProjectTask).where(ProjectTask.project_id == project_id))).scalars().all()
    return {**p.__dict__, "tasks": tasks}


@router.post("/", status_code=201)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    project = Project(**data.model_dump())
    if project.title:
        project.slug = project.title.lower().replace(" ", "-")
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


@router.put("/{project_id}")
async def update_project(project_id: int, data: ProjectUpdate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    await db.flush()
    await db.refresh(p)
    return p


@router.delete("/{project_id}", response_model=SuccessResponse)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(p)
    return SuccessResponse(message="Project deleted")


@router.post("/{project_id}/upload-image", response_model=SuccessResponse)
async def upload_project_image(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    result = await storage_service.upload_file(file, subfolder="projects")
    images = list(p.images or [])
    images.append(result["file_url"])
    p.images = images
    if not p.thumbnail_url:
        p.thumbnail_url = result["file_url"]
    await db.flush()
    return SuccessResponse(message="Image uploaded", data={"url": result["file_url"]})


@router.get("/{project_id}/tasks")
async def get_project_tasks(project_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    tasks = (await db.execute(select(ProjectTask).where(ProjectTask.project_id == project_id))).scalars().all()
    return {"items": tasks}


@router.post("/{project_id}/tasks", status_code=201)
async def create_project_task(project_id: int, data: ProjectTaskCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    task = ProjectTask(project_id=project_id, **data.model_dump())
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@router.patch("/{project_id}/tasks/{task_id}/complete", response_model=SuccessResponse)
async def toggle_project_task(project_id: int, task_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    task = (await db.execute(select(ProjectTask).where(and_(ProjectTask.id == task_id, ProjectTask.project_id == project_id)))).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.is_completed = not task.is_completed
    task.status = "done" if task.is_completed else "todo"
    await db.flush()
    return SuccessResponse(message="Task toggled")
