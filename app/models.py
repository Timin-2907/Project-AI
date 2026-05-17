import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Enum, Text, Boolean
)
from sqlalchemy.orm import relationship
from database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserStatus(str, enum.Enum):
    active   = "active"
    inactive = "inactive"
    banned   = "banned"


class VerifyStatus(str, enum.Enum):
    pending  = "pending"
    verified = "verified"
    expired  = "expired"


class LoginStatus(str, enum.Enum):
    success = "success"
    failed  = "failed"


class GenderEnum(str, enum.Enum):
    male   = "male"
    female = "female"
    other  = "other"


# ── Models ────────────────────────────────────────────────────────────────────

class Role(Base):
    __tablename__ = "Role"

    RoleID   = Column(Integer, primary_key=True, autoincrement=True)
    RoleName = Column(String(50), unique=True, nullable=False)

    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "User"

    UserID       = Column(Integer, primary_key=True, autoincrement=True)
    LastName     = Column(String(100), nullable=False)         # Họ và tên đệm
    FirstName    = Column(String(50),  nullable=False)         # Tên
    Email        = Column(String(150), unique=True, nullable=False)
    Phone        = Column(String(15),  unique=True, nullable=False)
    Gender       = Column(Enum(GenderEnum, name="gender_enum"), nullable=False)
    PasswordHash = Column(String(255), nullable=False)
    RoleID       = Column(Integer, ForeignKey("Role.RoleID"), nullable=False, default=1)
    Status       = Column(Enum(UserStatus, name="user_status"), default=UserStatus.inactive, nullable=False)
    CreatedAt    = Column(DateTime, default=datetime.utcnow, nullable=False)

    role            = relationship("Role", back_populates="users")
    tokens          = relationship("AuthToken",     back_populates="user", cascade="all, delete")
    verifications   = relationship("Verification",  back_populates="user", cascade="all, delete")
    password_resets = relationship("PasswordReset", back_populates="user", cascade="all, delete")
    login_history   = relationship("LoginHistory",  back_populates="user", cascade="all, delete")
    oauth_providers = relationship("OAuthProvider", back_populates="user", cascade="all, delete")


class AuthToken(Base):
    __tablename__ = "AuthToken"

    TokenID   = Column(Integer, primary_key=True, autoincrement=True)
    UserID    = Column(Integer, ForeignKey("User.UserID", ondelete="CASCADE"), nullable=False)
    Token     = Column(Text, nullable=False)
    ExpiresAt = Column(DateTime, nullable=False)
    CreatedAt = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="tokens")


class Verification(Base):
    __tablename__ = "Verification"

    VerificationID = Column(Integer, primary_key=True, autoincrement=True)
    UserID         = Column(Integer, ForeignKey("User.UserID", ondelete="CASCADE"), nullable=False)
    Code           = Column(String(10), nullable=False)
    ExpiresAt      = Column(DateTime, nullable=False)
    Status         = Column(Enum(VerifyStatus, name="verify_status"), default=VerifyStatus.pending, nullable=False)

    user = relationship("User", back_populates="verifications")


class PasswordReset(Base):
    __tablename__ = "PasswordReset"

    ResetID    = Column(Integer, primary_key=True, autoincrement=True)
    UserID     = Column(Integer, ForeignKey("User.UserID", ondelete="CASCADE"), nullable=False)
    ResetToken = Column(String(255), nullable=False)
    ExpiresAt  = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="password_resets")


class LoginHistory(Base):
    __tablename__ = "LoginHistory"

    HistoryID = Column(Integer, primary_key=True, autoincrement=True)
    UserID    = Column(Integer, ForeignKey("User.UserID", ondelete="CASCADE"), nullable=False)
    Status    = Column(Enum(LoginStatus, name="login_status"), nullable=False)
    LoginAt   = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="login_history")


class OAuthProvider(Base):
    __tablename__ = "OAuthProvider"

    OAuthID         = Column(Integer, primary_key=True, autoincrement=True)
    UserID          = Column(Integer, ForeignKey("User.UserID", ondelete="CASCADE"), nullable=False)
    Provider        = Column(String(50),  nullable=False)
    ProviderUserID  = Column(String(255), nullable=False)
    AccessTokenHash = Column(String(255))

    user = relationship("User", back_populates="oauth_providers")