from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from typing import Optional


# ── Auth Requests ──────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    last_name: str        # Họ và tên đệm (NGUYỄN TẤN)
    first_name: str       # Tên (PHÁT)
    email: EmailStr
    phone: str
    gender: str           # 'male' | 'female' | 'other'
    password: str
    confirm_password: str
    agree_terms: bool

    @field_validator("last_name")
    @classmethod
    def last_name_valid(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Họ và tên đệm không được để trống")
        if len(v) > 100:
            raise ValueError("Họ và tên đệm tối đa 100 ký tự")
        return v

    @field_validator("first_name")
    @classmethod
    def first_name_valid(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Tên không được để trống")
        if len(v) > 50:
            raise ValueError("Tên tối đa 50 ký tự")
        return v

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        v = v.strip().replace(" ", "")
        if not v.startswith("0") or not v.isdigit() or len(v) != 10:
            raise ValueError("Số điện thoại không hợp lệ (VD: 0912345678)")
        return v

    @field_validator("gender")
    @classmethod
    def gender_valid(cls, v):
        if v not in ("male", "female", "other"):
            raise ValueError("Giới tính không hợp lệ")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v):
        if len(v) < 6:
            raise ValueError("Mật khẩu phải ít nhất 6 ký tự")
        return v

    @field_validator("confirm_password")
    @classmethod
    def confirm_password_valid(cls, v):
        if len(v) < 6:
            raise ValueError("Xác nhận mật khẩu không hợp lệ")
        return v

    @field_validator("agree_terms")
    @classmethod
    def must_agree(cls, v):
        if not v:
            raise ValueError("Bạn phải đồng ý với điều khoản sử dụng")
        return v

    def model_post_init(self, __context):
        if self.password != self.confirm_password:
            raise ValueError("Mật khẩu xác nhận không khớp")


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
    last_name: str
    first_name: str
    full_name: str
    email: str
    phone: str
    gender: str
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