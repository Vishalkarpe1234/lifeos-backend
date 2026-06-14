from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, verify_refresh_token,
)
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.profile import Profile
from app.schemas.auth import (
    LoginRequest, PINLoginRequest, TokenResponse, RefreshTokenRequest,
    ChangePasswordRequest, SetPINRequest,
)
from app.schemas.common import SuccessResponse
from app.services.email_service import (
    create_and_send_otp, verify_otp, verify_otp_for_reset,
    get_email_by_reset_token, SUPER_ADMIN_EMAIL,
)
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["Authentication"])

SUPER_ADMIN = SUPER_ADMIN_EMAIL


# ── Registration schemas ──────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str


class ResendOTPRequest(BaseModel):
    email: EmailStr
    purpose: str = "verify_email"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyResetOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=SuccessResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email = request.email.lower().strip()

    if email == SUPER_ADMIN:
        raise HTTPException(status_code=400, detail="This email is reserved for the Super Admin.")

    repo = UserRepository(db)
    existing = await repo.get_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = User(
        email=email,
        hashed_password=get_password_hash(request.password),
        is_active=True,
        is_admin=False,
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    profile = Profile(user_id=user.id, full_name=request.full_name)
    db.add(profile)

    await create_and_send_otp(db, email, "verify_email")
    await db.commit()

    return SuccessResponse(message=f"Account created. OTP sent to {email}.")


@router.post("/verify-email", response_model=SuccessResponse)
async def verify_email(request: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    email = request.email.lower().strip()
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not await verify_otp(db, email, request.otp, "verify_email"):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    await repo.update(user, email_verified=True)
    await db.commit()
    return SuccessResponse(message="Email verified successfully")


@router.post("/resend-otp", response_model=SuccessResponse)
async def resend_otp(request: ResendOTPRequest, db: AsyncSession = Depends(get_db)):
    email = request.email.lower().strip()
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await create_and_send_otp(db, email, request.purpose)
    await db.commit()
    return SuccessResponse(message="OTP sent")


@router.post("/forgot-password", response_model=SuccessResponse)
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    email = request.email.lower().strip()
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if not user:
        # Don't reveal whether email exists
        return SuccessResponse(message="If that email exists, an OTP has been sent.")

    await create_and_send_otp(db, email, "reset_password")
    await db.commit()
    return SuccessResponse(message="OTP sent to your email")


@router.post("/verify-reset-otp")
async def verify_reset_otp(request: VerifyResetOTPRequest, db: AsyncSession = Depends(get_db)):
    email = request.email.lower().strip()
    token = await verify_otp_for_reset(db, email, request.otp)
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    await db.commit()
    return {"reset_token": token}


@router.post("/reset-password", response_model=SuccessResponse)
async def reset_password(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    email = await get_email_by_reset_token(db, request.reset_token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await repo.update(user, hashed_password=get_password_hash(request.new_password))
    await db.commit()
    return SuccessResponse(message="Password reset successfully")


# ── Standard auth ─────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await repo.get_by_email(request.email.lower().strip())
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    email_verified = getattr(user, 'email_verified', True)
    if not email_verified and user.email != SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Please verify your email first")

    await repo.update(user, last_login=datetime.now(timezone.utc))
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login/pin", response_model=TokenResponse)
async def login_with_pin(request: PINLoginRequest, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await repo.get_by_email(request.email.lower())
    if not user or not user.pin_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="PIN not set")
    if not verify_password(request.pin, user.pin_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    user_id = verify_refresh_token(request.refresh_token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(request: ChangePasswordRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    repo = UserRepository(db)
    await repo.update(current_user, hashed_password=get_password_hash(request.new_password))
    return SuccessResponse(message="Password changed successfully")


@router.post("/set-pin", response_model=SuccessResponse)
async def set_pin(request: SetPINRequest, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Password incorrect")
    repo = UserRepository(db)
    await repo.update(current_user, pin_hash=get_password_hash(request.pin))
    return SuccessResponse(message="PIN set successfully")


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_admin": current_user.is_admin,
        "is_super_admin": current_user.email == SUPER_ADMIN,
        "email_verified": getattr(current_user, 'email_verified', True),
        "biometric_enabled": current_user.biometric_enabled,
        "totp_enabled": current_user.totp_enabled,
        "last_login": current_user.last_login,
    }


@router.post("/logout", response_model=SuccessResponse)
async def logout(current_user=Depends(get_current_user)):
    return SuccessResponse(message="Logged out successfully")


class ChangeEmailRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/change-email", response_model=SuccessResponse)
async def change_email(
    data: ChangeEmailRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    existing = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")
    current_user.email = data.email
    await db.flush()
    return SuccessResponse(message="Email updated successfully")


class DeleteAccountRequest(BaseModel):
    password: str

@router.delete("/delete-account", response_model=SuccessResponse)
async def delete_account(
    data: DeleteAccountRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    from app.services.email_service import SUPER_ADMIN_EMAIL
    if current_user.email == SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Cannot delete admin account")
    await db.delete(current_user)
    return SuccessResponse(message="Account deleted")
