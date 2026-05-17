import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from database import get_db

from app.models import (
    User,
    Role,
    AuthToken,
    Verification,
    PasswordReset,
    LoginHistory,
    VerifyStatus,
    LoginStatus,
)

from app.schemas import (
    RegisterRequest,
    LoginRequest,
    VerifyEmailRequest,
    ResendVerificationRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    RefreshTokenRequest,
    LogoutRequest,
    LoginResponse,
    MessageResponse,
    UserInfo,
)

from app.utils.security import (
    hash_password,
    verify_password,
    generate_otp,
    generate_reset_token,
    create_access_token,
    create_refresh_token,
    decode_token,
)

from app.utils.email import (
    send_verification_email,
    send_password_reset_email,
)

from dependencies import get_current_user
from config import settings

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ─────────────────────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────────────────────
@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):

    # Check email
    email_check = await db.execute(
        select(User).where(User.Email == data.email)
    )

    if email_check.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Email đã tồn tại"
        )

    # Check phone
    phone_check = await db.execute(
        select(User).where(User.Phone == data.phone)
    )

    if phone_check.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Số điện thoại đã tồn tại"
        )

    # Get role
    role_result = await db.execute(
        select(Role).where(Role.RoleName == "user")
    )

    role = role_result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=500,
            detail="Không tìm thấy role mặc định"
        )

    # Create user
    user = User(
        LastName=data.last_name.strip(),
        FirstName=data.first_name.strip(),
        Email=data.email,
        Phone=data.phone,
        Gender=data.gender,
        PasswordHash=hash_password(data.password),
        RoleID=role.RoleID,
    )

    db.add(user)
    await db.flush()

    # Create OTP
    code = generate_otp()

    verification = Verification(
        UserID=user.UserID,
        Code=code,
        ExpiresAt=datetime.utcnow() + timedelta(minutes=10),
    )

    db.add(verification)

    await db.commit()

    asyncio.create_task(
        send_verification_email(data.email, code)
    )

    return MessageResponse(
        success=True,
        message="Đăng ký thành công. Vui lòng kiểm tra email."
    )


# ─────────────────────────────────────────────────────────────
# VERIFY EMAIL
# ─────────────────────────────────────────────────────────────
@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    data: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db)
):

    result = await db.execute(
        select(User).where(User.Email == data.email)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy tài khoản"
        )

    if user.Status.value == "active":
        raise HTTPException(
            status_code=400,
            detail="Tài khoản đã xác minh"
        )

    verification_result = await db.execute(
        select(Verification).where(
            and_(
                Verification.UserID == user.UserID,
                Verification.Code == data.code,
                Verification.Status == VerifyStatus.pending,
                Verification.ExpiresAt > datetime.utcnow(),
            )
        )
    )

    verification = verification_result.scalar_one_or_none()

    if not verification:
        raise HTTPException(
            status_code=400,
            detail="Mã xác minh không hợp lệ hoặc hết hạn"
        )

    user.Status = "active"
    verification.Status = VerifyStatus.verified

    await db.commit()

    return MessageResponse(
        success=True,
        message="Xác minh email thành công"
    )


# ─────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):

    result = await db.execute(
        select(User).where(User.Email == data.email)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Email hoặc mật khẩu không đúng"
        )

    if user.Status.value == "inactive":
        raise HTTPException(
            status_code=403,
            detail="Tài khoản chưa xác minh"
        )

    if not verify_password(data.password, user.PasswordHash):

        db.add(
            LoginHistory(
                UserID=user.UserID,
                Status=LoginStatus.failed,
            )
        )

        await db.commit()

        raise HTTPException(
            status_code=401,
            detail="Email hoặc mật khẩu không đúng"
        )

    db.add(
        LoginHistory(
            UserID=user.UserID,
            Status=LoginStatus.success,
        )
    )

    role_result = await db.execute(
        select(Role).where(Role.RoleID == user.RoleID)
    )

    role = role_result.scalar_one()

    payload = {
        "user_id": user.UserID,
        "email": user.Email,
        "role": role.RoleName,
    }

    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    token = AuthToken(
        UserID=user.UserID,
        Token=refresh_token,
        ExpiresAt=datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        ),
    )

    db.add(token)

    await db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserInfo(
            id=user.UserID,
            last_name=user.LastName,
            first_name=user.FirstName,
            full_name=f"{user.LastName} {user.FirstName}",
            email=user.Email,
            phone=user.Phone,
            gender=user.Gender.value,
            role=role.RoleName,
            status=user.Status.value,
            created_at=user.CreatedAt,
        ),
    )


# ─────────────────────────────────────────────────────────────
# REFRESH TOKEN
# ─────────────────────────────────────────────────────────────
@router.post("/refresh-token")
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):

    result = await db.execute(
        select(AuthToken).where(
            and_(
                AuthToken.Token == data.refresh_token,
                AuthToken.ExpiresAt > datetime.utcnow(),
            )
        )
    )

    token_row = result.scalar_one_or_none()

    if not token_row:
        raise HTTPException(
            status_code=401,
            detail="Refresh token không hợp lệ"
        )

    payload = decode_token(data.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Token không hợp lệ"
        )

    new_access = create_access_token({
        "user_id": payload["user_id"],
        "email": payload["email"],
        "role": payload["role"],
    })

    return {
        "success": True,
        "access_token": new_access,
        "token_type": "bearer",
    }


# ─────────────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────────────
@router.post("/logout", response_model=MessageResponse)
async def logout(
    data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    result = await db.execute(
        select(AuthToken).where(
            AuthToken.Token == data.refresh_token
        )
    )

    token_row = result.scalar_one_or_none()

    if token_row:
        await db.delete(token_row)
        await db.commit()

    return MessageResponse(
        success=True,
        message="Đăng xuất thành công"
    )


# ─────────────────────────────────────────────────────────────
# GET ME
# ─────────────────────────────────────────────────────────────
@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    role_result = await db.execute(
        select(Role).where(
            Role.RoleID == current_user.RoleID
        )
    )

    role = role_result.scalar_one()

    return {
        "success": True,
        "data": {
            "id": current_user.UserID,
            "last_name": current_user.LastName,
            "first_name": current_user.FirstName,
            "full_name": f"{current_user.LastName} {current_user.FirstName}",
            "email": current_user.Email,
            "phone": current_user.Phone,
            "gender": current_user.Gender.value,
            "role": role.RoleName,
            "status": current_user.Status.value,
            "created_at": current_user.CreatedAt,
        },
    }