from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PINLoginRequest(BaseModel):
    email: EmailStr
    pin: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class SetPINRequest(BaseModel):
    pin: str
    password: str

    @field_validator("pin")
    @classmethod
    def pin_length(cls, v):
        if not v.isdigit() or len(v) not in (4, 6):
            raise ValueError("PIN must be 4 or 6 digits")
        return v


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code_url: str
    backup_codes: list[str]


class TOTPVerifyRequest(BaseModel):
    code: str


class BiometricRegisterRequest(BaseModel):
    public_key: str
    device_id: str
