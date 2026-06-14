from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc, asc
from typing import Optional
from pydantic import BaseModel
from datetime import date

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.research import ResearchPublication, Conference
from app.schemas.common import SuccessResponse, PaginatedResponse

router = APIRouter(prefix="/research", tags=["Research"])


class PublicationCreate(BaseModel):
    title: str
    abstract: Optional[str] = None
    authors: list[str] = []
    journal_name: Optional[str] = None
    conference_name: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    year: Optional[int] = None
    publication_date: Optional[date] = None
    pub_type: str = "journal"
    status: str = "published"
    is_indexed: bool = False
    index_type: Optional[str] = None
    citation_count: int = 0
    pdf_url: Optional[str] = None
    external_url: Optional[str] = None
    keywords: list[str] = []
    notes: Optional[str] = None
    bibtex: Optional[str] = None
    is_featured: bool = False
    issn: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None


class PublicationUpdate(PublicationCreate):
    title: Optional[str] = None


class ConferenceCreate(BaseModel):
    name: str
    location: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    website: Optional[str] = None
    paper_title: Optional[str] = None
    presentation_type: str = "oral"
    status: str = "presented"
    notes: Optional[str] = None
    certificate_url: Optional[str] = None


@router.get("/publications")
async def list_publications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    pub_type: Optional[str] = None,
    status: Optional[str] = None,
    year: Optional[int] = None,
    is_featured: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = select(ResearchPublication)
    count_q = select(func.count()).select_from(ResearchPublication)
    filters = []

    if search:
        filters.append(
            or_(
                ResearchPublication.title.ilike(f"%{search}%"),
                ResearchPublication.abstract.ilike(f"%{search}%"),
            )
        )
    if pub_type:
        filters.append(ResearchPublication.pub_type == pub_type)
    if status:
        filters.append(ResearchPublication.status == status)
    if year:
        filters.append(ResearchPublication.year == year)
    if is_featured is not None:
        filters.append(ResearchPublication.is_featured == is_featured)

    if filters:
        from sqlalchemy import and_
        query = query.where(and_(*filters))
        count_q = count_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar()
    skip = (page - 1) * page_size
    items = (await db.execute(query.order_by(desc(ResearchPublication.year)).offset(skip).limit(page_size))).scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/publications/{pub_id}")
async def get_publication(pub_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    pub = (await db.execute(select(ResearchPublication).where(ResearchPublication.id == pub_id))).scalar_one_or_none()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    return pub


@router.post("/publications", status_code=status.HTTP_201_CREATED)
async def create_publication(
    data: PublicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    pub = ResearchPublication(**data.model_dump())
    db.add(pub)
    await db.flush()
    await db.refresh(pub)
    return pub


@router.put("/publications/{pub_id}")
async def update_publication(
    pub_id: int,
    data: PublicationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    pub = (await db.execute(select(ResearchPublication).where(ResearchPublication.id == pub_id))).scalar_one_or_none()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(pub, k, v)
    await db.flush()
    await db.refresh(pub)
    return pub


@router.delete("/publications/{pub_id}", response_model=SuccessResponse)
async def delete_publication(pub_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    pub = (await db.execute(select(ResearchPublication).where(ResearchPublication.id == pub_id))).scalar_one_or_none()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    await db.delete(pub)
    return SuccessResponse(message="Publication deleted")


@router.get("/conferences")
async def list_conferences(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    items = (await db.execute(select(Conference).order_by(desc(Conference.start_date)))).scalars().all()
    return {"items": items, "total": len(items)}


@router.post("/conferences", status_code=status.HTTP_201_CREATED)
async def create_conference(data: ConferenceCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    conf = Conference(**data.model_dump())
    db.add(conf)
    await db.flush()
    await db.refresh(conf)
    return conf


@router.put("/conferences/{conf_id}")
async def update_conference(conf_id: int, data: ConferenceCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    conf = (await db.execute(select(Conference).where(Conference.id == conf_id))).scalar_one_or_none()
    if not conf:
        raise HTTPException(status_code=404, detail="Conference not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(conf, k, v)
    await db.flush()
    await db.refresh(conf)
    return conf


@router.delete("/conferences/{conf_id}", response_model=SuccessResponse)
async def delete_conference(conf_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    conf = (await db.execute(select(Conference).where(Conference.id == conf_id))).scalar_one_or_none()
    if not conf:
        raise HTTPException(status_code=404, detail="Conference not found")
    await db.delete(conf)
    return SuccessResponse(message="Conference deleted")


@router.get("/stats")
async def research_stats(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    total_pubs = (await db.execute(select(func.count()).select_from(ResearchPublication))).scalar()
    total_conf = (await db.execute(select(func.count()).select_from(Conference))).scalar()
    total_citations = (await db.execute(select(func.sum(ResearchPublication.citation_count)))).scalar() or 0
    indexed = (await db.execute(select(func.count()).select_from(ResearchPublication).where(ResearchPublication.is_indexed == True))).scalar()
    return {
        "total_publications": total_pubs,
        "total_conferences": total_conf,
        "total_citations": total_citations,
        "indexed_publications": indexed,
    }
