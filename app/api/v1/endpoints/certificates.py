from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import date

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.certificate import Certificate
from app.services.storage_service import StorageService

router = APIRouter(prefix="/certificates", tags=["certificates"])
_storage = StorageService()


@router.get("/")
async def list_certificates(
    category: Optional[str] = None,
    is_featured: Optional[bool] = None,
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = select(Certificate)
    if category:
        q = q.where(Certificate.category == category)
    if is_featured is not None:
        q = q.where(Certificate.is_featured == is_featured)
    q = q.order_by(Certificate.order_index, Certificate.issue_date.desc())
    offset = (page - 1) * page_size
    result = await db.execute(q.offset(offset).limit(page_size))
    certs = result.scalars().all()
    total = (await db.execute(select(func.count()).select_from(Certificate))).scalar_one()
    return {"items": [_cert_dict(c) for c in certs], "total": total, "page": page, "page_size": page_size}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_certificate(data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    cert = Certificate(
        title=data.get("title", ""),
        issuing_organization=data.get("issuing_organization", ""),
        issue_date=date.fromisoformat(data["issue_date"]) if data.get("issue_date") else None,
        expiry_date=date.fromisoformat(data["expiry_date"]) if data.get("expiry_date") else None,
        credential_id=data.get("credential_id"),
        credential_url=data.get("credential_url"),
        certificate_url=data.get("certificate_url"),
        category=data.get("category", "general"),
        skills=data.get("skills", []),
        description=data.get("description"),
        is_featured=data.get("is_featured", False),
        is_expired=data.get("is_expired", False),
        tags=data.get("tags", []),
        order_index=data.get("order_index", 0),
    )
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return _cert_dict(cert)


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    total = (await db.execute(select(func.count()).select_from(Certificate))).scalar_one()
    featured = (await db.execute(select(func.count()).select_from(Certificate).where(Certificate.is_featured == True))).scalar_one()
    return {"total": total, "featured": featured}


@router.get("/{cert_id}")
async def get_certificate(cert_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return _cert_dict(await _get_or_404(cert_id, db))


@router.put("/{cert_id}")
async def update_certificate(cert_id: int, data: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    cert = await _get_or_404(cert_id, db)
    updatable = {"title", "issuing_organization", "credential_id", "credential_url", "certificate_url", "category", "skills", "description", "is_featured", "is_expired", "tags", "order_index"}
    for k, v in data.items():
        if k in updatable:
            setattr(cert, k, v)
    if "issue_date" in data and data["issue_date"]:
        cert.issue_date = date.fromisoformat(data["issue_date"])
    if "expiry_date" in data and data["expiry_date"]:
        cert.expiry_date = date.fromisoformat(data["expiry_date"])
    await db.commit()
    await db.refresh(cert)
    return _cert_dict(cert)


@router.post("/{cert_id}/image")
async def upload_certificate_image(
    cert_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    cert = await _get_or_404(cert_id, db)
    file_info = await _storage.upload_file(file, subfolder="certificates")
    cert.certificate_url = file_info["file_url"]
    await db.commit()
    return {"certificate_url": cert.certificate_url}


@router.patch("/{cert_id}/featured")
async def toggle_featured(cert_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    cert = await _get_or_404(cert_id, db)
    cert.is_featured = not cert.is_featured
    await db.commit()
    return {"id": cert.id, "is_featured": cert.is_featured}


@router.delete("/{cert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certificate(cert_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_admin)):
    cert = await _get_or_404(cert_id, db)
    await db.delete(cert)
    await db.commit()


async def _get_or_404(cert_id: int, db: AsyncSession) -> Certificate:
    result = await db.execute(select(Certificate).where(Certificate.id == cert_id))
    cert = result.scalar_one_or_none()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return cert


def _cert_dict(c: Certificate) -> dict:
    return {
        "id": c.id, "title": c.title, "issuing_organization": c.issuing_organization,
        "issue_date": c.issue_date.isoformat() if c.issue_date else None,
        "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
        "credential_id": c.credential_id, "credential_url": c.credential_url,
        "certificate_url": c.certificate_url, "category": c.category,
        "skills": c.skills, "description": c.description,
        "is_featured": c.is_featured, "is_expired": c.is_expired,
        "tags": c.tags, "order_index": c.order_index,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
