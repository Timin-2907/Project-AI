import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import settings


async def _send(to: str, subject: str, html: str):
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.EMAIL_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            username=settings.EMAIL_USER,
            password=settings.EMAIL_PASS,
            start_tls=True,
        )
    except Exception as e:
        print(f"[Email Error] {e}")


async def send_verification_email(to: str, code: str):
    await _send(
        to, "Xác minh tài khoản của bạn",
        f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px;
                    border:1px solid #eee;border-radius:8px">
            <h2 style="color:#1a1a2e">Xác minh tài khoản</h2>
            <p>Mã xác minh của bạn là:</p>
            <div style="font-size:36px;font-weight:bold;letter-spacing:8px;
                        color:#4f46e5;padding:16px 0">{code}</div>
            <p style="color:#666">Mã có hiệu lực trong <strong>10 phút</strong>.
               Không chia sẻ mã này với ai.</p>
        </div>
        """,
    )


async def send_password_reset_email(to: str, reset_link: str):
    await _send(
        to, "Đặt lại mật khẩu",
        f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px;
                    border:1px solid #eee;border-radius:8px">
            <h2 style="color:#1a1a2e">Đặt lại mật khẩu</h2>
            <p>Nhấn vào nút bên dưới để đặt lại mật khẩu:</p>
            <a href="{reset_link}"
               style="display:inline-block;margin:16px 0;padding:12px 24px;
                      background:#4f46e5;color:#fff;text-decoration:none;
                      border-radius:6px;font-weight:bold">Đặt lại mật khẩu</a>
            <p style="color:#666">Link có hiệu lực trong <strong>15 phút</strong>.
               Nếu bạn không yêu cầu, hãy bỏ qua email này.</p>
        </div>
        """,
    )