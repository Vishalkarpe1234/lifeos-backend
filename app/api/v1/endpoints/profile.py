from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.profile import Profile
from app.models.media import MediaFile
from app.schemas.profile import ProfileUpdate, ProfileResponse
from app.schemas.common import SuccessResponse
from app.services.storage_service import storage_service

router = APIRouter(prefix="/profile", tags=["Profile"])

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]
ALLOWED_DOC_TYPES = ["application/pdf"]


async def _get_or_create_profile(user_id: int, db: AsyncSession) -> Profile:
    result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = Profile(user_id=user_id)
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
    return profile


@router.get("/", response_model=ProfileResponse)
async def get_profile(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_or_create_profile(current_user.id, db)
    return profile


@router.put("/", response_model=ProfileResponse)
async def update_profile(
    data: ProfileUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_or_create_profile(current_user.id, db)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    await db.flush()
    await db.refresh(profile)
    return profile


@router.post("/photo", response_model=SuccessResponse)
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image type")

    result = await storage_service.upload_file(file, subfolder="profile_photos", allowed_types=ALLOWED_IMAGE_TYPES)
    profile = await _get_or_create_profile(current_user.id, db)
    profile.profile_photo_url = result["file_url"]
    await db.flush()

    media = MediaFile(
        filename=result["filename"],
        original_filename=result["original_filename"],
        file_path=result["file_path"],
        file_url=result["file_url"],
        file_type="image",
        mime_type=result["mime_type"],
        file_size=result["file_size"],
        category="profile",
        module="profile",
    )
    db.add(media)
    await db.flush()

    return SuccessResponse(message="Profile photo updated", data={"url": result["file_url"]})


@router.post("/cover", response_model=SuccessResponse)
async def upload_cover_image(
    file: UploadFile = File(...),
    current_user=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image type")

    result = await storage_service.upload_file(file, subfolder="covers", allowed_types=ALLOWED_IMAGE_TYPES)
    profile = await _get_or_create_profile(current_user.id, db)
    profile.cover_image_url = result["file_url"]
    await db.flush()
    return SuccessResponse(message="Cover image updated", data={"url": result["file_url"]})


@router.post("/resume", response_model=SuccessResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF allowed")

    result = await storage_service.upload_file(file, subfolder="resumes")
    profile = await _get_or_create_profile(current_user.id, db)
    profile.resume_url = result["file_url"]
    await db.flush()
    return SuccessResponse(message="Resume uploaded", data={"url": result["file_url"]})
