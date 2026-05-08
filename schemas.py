from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from typing import Optional


# ── Auth Requests ──────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v):
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username phải từ 3–50 ký tự")
        if not v.replace("_", "").isalnum():
            raise ValueError("Username chỉ chứa chữ cái, số và dấu _")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v):
        if len(v) < 6:
            raise ValueError("Mật khẩu phải ít nhất 6 ký tự")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def password_valid(cls, v):
        if len(v) < 6:
            raise ValueError("Mật khẩu phải ít nhất 6 ký tự")
        return v


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


# ── Auth Responses ─────────────────────────────────────────────────────────────

class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    role: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserInfo


class MessageResponse(BaseModel):
    success: bool
    message: str


class LoginHistoryItem(BaseModel):
    history_id: int
    status: str
    login_at: datetime