from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.contact import Contact

router = APIRouter(prefix="/contacts", tags=["Contacts"])


class ContactCreate(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    relationship_type: Optional[str] = None
    birthday: Optional[date] = None
    notes: Optional[str] = None


@router.get("")
async def list_contacts(q: Optional[str] = None, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query = select(Contact).where(Contact.user_id == current_user.id)
    if q:
        query = query.where(or_(Contact.full_name.ilike(f"%{q}%"), Contact.email.ilike(f"%{q}%"), Contact.company.ilike(f"%{q}%")))
    result = await db.execute(query.order_by(Contact.full_name))
    contacts = result.scalars().all()
    return [
        {
            "id": c.id,
            "full_name": c.full_name,
            "email": c.email,
            "phone": c.phone,
            "company": c.company,
            "job_title": c.job_title,
            "relationship_type": c.relationship_type,
            "is_favorite": c.is_favorite,
        }
        for c in contacts
    ]


@router.post("")
async def create_contact(body: ContactCreate, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    contact = Contact(user_id=current_user.id, **body.model_dump(exclude_none=True))
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return {"id": contact.id, "full_name": contact.full_name}


@router.delete("/{contact_id}")
async def delete_contact(contact_id: int, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contact).where(Contact.id == contact_id, Contact.user_id == current_user.id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    await db.delete(contact)
    await db.commit()
    return {"ok": True}
