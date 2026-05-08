import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database import get_db
from models import User, Role, AuthToken, Verification, PasswordReset, LoginHistory, VerifyStatus, LoginStatus
from schemas import (
    RegisterRequest, LoginRequest, VerifyEmailRequest, ResendVerificationRequest,
    ForgotPasswordRequest, ResetPasswordRequest, RefreshTokenRequest, LogoutRequest,
    LoginResponse, MessageResponse, UserInfo, LoginHistoryItem,
)
from utils.security import (
    hash_password, verify_password, generate_otp, generate_reset_token,
    create_access_token, create_refresh_token, decode_token,
)
from utils.email import send_verification_email, send_password_reset_email
from dependencies import get_current_user
from config import settings

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/register
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Kiểm tra trùng email / username
    result = await db.execute(
        select(User).where((User.Email == data.email) | (User.Username == data.username))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email hoặc username đã tồn tại")

    # Lấy role mặc định
    role_result = await db.execute(select(Role).where(Role.RoleName == "user"))
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=500, detail="Không tìm thấy role mặc định")

    # Tạo user
    user = User(
        Username=data.username,
        Email=data.email,
        PasswordHash=hash_password(data.password),
        RoleID=role.RoleID,
    )
    db.add(user)
    await db.flush()  # lấy UserID ngay

    # Tạo OTP
    code = generate_otp()
    verification = Verification(
        UserID=user.UserID,
        Code=code,
        ExpiresAt=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(verification)
    await db.commit()

    # Gửi email không chặn response
    asyncio.create_task(send_verification_email(data.email, code))

    return MessageResponse(
        success=True,
        message="Đăng ký thành công. Vui lòng kiểm tra email để xác minh tài khoản.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/verify-email
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.Email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    if user.Status.value == "active":
        raise HTTPException(status_code=400, detail="Tài khoản đã được xác minh")

    v_result = await db.execute(
        select(Verification).where(
            and_(
                Verification.UserID == user.UserID,
                Verification.Code == data.code,
                Verification.Status == VerifyStatus.pending,
                Verification.ExpiresAt > datetime.utcnow(),
            )
        ).order_by(Verification.VerificationID.desc()).limit(1)
    )
    verification = v_result.scalar_one_or_none()
    if not verification:
        raise HTTPException(status_code=400, detail="Mã xác minh không hợp lệ hoặc đã hết hạn")

    user.Status = "active"
    verification.Status = VerifyStatus.verified
    await db.commit()

    return MessageResponse(success=True, message="Xác minh tài khoản thành công. Bạn có thể đăng nhập.")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/resend-verification
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(data: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.Email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    if user.Status.value == "active":
        raise HTTPException(status_code=400, detail="Tài khoản đã được xác minh")

    code = generate_otp()
    db.add(Verification(
        UserID=user.UserID,
        Code=code,
        ExpiresAt=datetime.utcnow() + timedelta(minutes=10),
    ))
    await db.commit()

    asyncio.create_task(send_verification_email(data.email, code))
    return MessageResponse(success=True, message="Mã xác minh mới đã được gửi")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/login
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.Email == data.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")

    status_val = user.Status.value if hasattr(user.Status, "value") else user.Status
    if status_val == "inactive":
        raise HTTPException(status_code=403, detail="Tài khoản chưa được xác minh. Vui lòng kiểm tra email.")
    if status_val == "banned":
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")

    is_match = verify_password(data.password, user.PasswordHash)

    # Ghi lịch sử
    db.add(LoginHistory(
        UserID=user.UserID,
        Status=LoginStatus.success if is_match else LoginStatus.failed,
    ))

    if not is_match:
        await db.commit()
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")

    # Lấy role name
    role_result = await db.execute(select(Role).where(Role.RoleID == user.RoleID))
    role = role_result.scalar_one()

    payload = {"user_id": user.UserID, "email": user.Email, "role": role.RoleName}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    db.add(AuthToken(
        UserID=user.UserID,
        Token=refresh_token,
        ExpiresAt=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    await db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserInfo(
            id=user.UserID,
            username=user.Username,
            email=user.Email,
            role=role.RoleName,
            status=status_val,
            created_at=user.CreatedAt,
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/refresh-token
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/refresh-token")
async def refresh_token(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuthToken).where(
            and_(AuthToken.Token == data.refresh_token, AuthToken.ExpiresAt > datetime.utcnow())
        )
    )
    token_row = result.scalar_one_or_none()
    if not token_row:
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ hoặc đã hết hạn")

    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ")

    new_access = create_access_token({"user_id": payload["user_id"], "email": payload["email"], "role": payload["role"]})
    return {"success": True, "access_token": new_access, "token_type": "bearer"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/logout
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/logout", response_model=MessageResponse)
async def logout(data: LogoutRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuthToken).where(AuthToken.Token == data.refresh_token))
    token_row = result.scalar_one_or_none()
    if token_row:
        await db.delete(token_row)
        await db.commit()
    return MessageResponse(success=True, message="Đăng xuất thành công")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/forgot-password
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    GENERIC_MSG = "Nếu email tồn tại, link đặt lại mật khẩu sẽ được gửi"

    result = await db.execute(select(User).where(User.Email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        return MessageResponse(success=True, message=GENERIC_MSG)

    reset_token = generate_reset_token()
    db.add(PasswordReset(
        UserID=user.UserID,
        ResetToken=reset_token,
        ExpiresAt=datetime.utcnow() + timedelta(minutes=15),
    ))
    await db.commit()

    reset_link = f"{settings.CLIENT_URL}/reset-password?token={reset_token}"
    asyncio.create_task(send_password_reset_email(data.email, reset_link))

    return MessageResponse(success=True, message=GENERIC_MSG)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/reset-password
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PasswordReset).where(
            and_(
                PasswordReset.ResetToken == data.token,
                PasswordReset.ExpiresAt > datetime.utcnow(),
            )
        ).order_by(PasswordReset.ResetID.desc()).limit(1)
    )
    reset_row = result.scalar_one_or_none()
    if not reset_row:
        raise HTTPException(status_code=400, detail="Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn")

    user_result = await db.execute(select(User).where(User.UserID == reset_row.UserID))
    user = user_result.scalar_one()
    user.PasswordHash = hash_password(data.password)

    # Xóa tất cả reset tokens của user
    all_resets = await db.execute(select(PasswordReset).where(PasswordReset.UserID == reset_row.UserID))
    for r in all_resets.scalars().all():
        await db.delete(r)

    await db.commit()
    return MessageResponse(success=True, message="Mật khẩu đã được đặt lại thành công")


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/auth/me   (Protected)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role_result = await db.execute(select(Role).where(Role.RoleID == current_user.RoleID))
    role = role_result.scalar_one()
    return {
        "success": True,
        "data": {
            "id": current_user.UserID,
            "username": current_user.Username,
            "email": current_user.Email,
            "role": role.RoleName,
            "status": current_user.Status.value,
            "created_at": current_user.CreatedAt,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/auth/login-history   (Protected)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/login-history")
async def get_login_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoginHistory)
        .where(LoginHistory.UserID == current_user.UserID)
        .order_by(LoginHistory.LoginAt.desc())
        .limit(20)
    )
    history = result.scalars().all()
    return {
        "success": True,
        "data": [
            {"history_id": h.HistoryID, "status": h.Status.value, "login_at": h.LoginAt}
            for h in history
        ],
    }