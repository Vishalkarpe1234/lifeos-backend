import asyncio
import logging
import random
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

SUPER_ADMIN_EMAIL = "karpevishal2712001@gmail.com"


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def generate_reset_token() -> str:
    return secrets.token_hex(32)


def _try_send_smtp(to_email: str, subject: str, html: str) -> bool:
    try:
        from app.core.config import settings
        if not getattr(settings, 'SMTP_HOST', None) or not getattr(settings, 'SMTP_USER', None):
            return False
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = getattr(settings, 'SMTP_USER', '')
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(settings.SMTP_HOST, getattr(settings, 'SMTP_PORT', 587)) as s:
            s.starttls()
            s.login(settings.SMTP_USER, getattr(settings, 'SMTP_PASSWORD', ''))
            s.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        logger.debug(f"SMTP send failed: {e}")
        return False


async def send_otp_email(to_email: str, otp: str, purpose: str) -> None:
    if purpose == "verify_email":
        subject = "VishalOS – Verify Your Email"
        html = f"""
<div style="font-family:Inter,sans-serif;max-width:560px;margin:0 auto;background:#f8f9ff;padding:40px;border-radius:20px;">
  <div style="text-align:center;margin-bottom:28px;">
    <div style="display:inline-block;background:linear-gradient(135deg,#6366F1,#8B5CF6);padding:14px 22px;border-radius:16px;">
      <span style="color:white;font-size:22px;font-weight:900;letter-spacing:-0.5px;">V∞ VishalOS</span>
    </div>
  </div>
  <h2 style="color:#1e1e3f;text-align:center;font-size:22px;margin-bottom:8px;">Verify Your Email</h2>
  <p style="color:#5c5f7a;text-align:center;font-size:14px;margin-bottom:28px;">Use this 6-digit OTP to verify your account:</p>
  <div style="background:linear-gradient(135deg,#6366F1,#8B5CF6);border-radius:16px;padding:28px;text-align:center;margin:0 0 24px;">
    <span style="color:white;font-size:40px;font-weight:900;letter-spacing:12px;">{otp}</span>
  </div>
  <p style="color:#9395b0;font-size:12px;text-align:center;">Expires in 10 minutes. Never share this OTP.</p>
</div>"""
    else:
        subject = "VishalOS – Reset Your Password"
        html = f"""
<div style="font-family:Inter,sans-serif;max-width:560px;margin:0 auto;background:#f8f9ff;padding:40px;border-radius:20px;">
  <div style="text-align:center;margin-bottom:28px;">
    <div style="display:inline-block;background:linear-gradient(135deg,#6366F1,#8B5CF6);padding:14px 22px;border-radius:16px;">
      <span style="color:white;font-size:22px;font-weight:900;">V∞ VishalOS</span>
    </div>
  </div>
  <h2 style="color:#1e1e3f;text-align:center;">Reset Password</h2>
  <p style="color:#5c5f7a;text-align:center;font-size:14px;">Use this OTP to reset your password:</p>
  <div style="background:linear-gradient(135deg,#EF4444,#EC4899);border-radius:16px;padding:28px;text-align:center;margin:24px 0;">
    <span style="color:white;font-size:40px;font-weight:900;letter-spacing:12px;">{otp}</span>
  </div>
  <p style="color:#9395b0;font-size:12px;text-align:center;">Expires in 10 minutes.</p>
</div>"""

    sent = await asyncio.to_thread(_try_send_smtp, to_email, subject, html)
    if not sent:
        logger.info(f"[DEV OTP] {to_email} | {purpose} | OTP: {otp}")


async def create_and_send_otp(db: AsyncSession, email: str, purpose: str) -> str:
    from app.models.otp import EmailOTP

    result = await db.execute(
        select(EmailOTP).where(and_(EmailOTP.email == email, EmailOTP.purpose == purpose, EmailOTP.used == False))
    )
    for old in result.scalars().all():
        old.used = True

    otp_code = generate_otp()
    record = EmailOTP(
        email=email,
        otp=otp_code,
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        used=False,
    )
    db.add(record)
    await db.flush()

    asyncio.create_task(send_otp_email(email, otp_code, purpose))
    return otp_code


async def verify_otp(db: AsyncSession, email: str, otp: str, purpose: str) -> bool:
    from app.models.otp import EmailOTP

    result = await db.execute(
        select(EmailOTP).where(and_(
            EmailOTP.email == email,
            EmailOTP.otp == otp,
            EmailOTP.purpose == purpose,
            EmailOTP.used == False,
            EmailOTP.expires_at > datetime.now(timezone.utc),
        ))
    )
    record = result.scalar_one_or_none()
    if not record:
        return False
    record.used = True
    return True


async def verify_otp_for_reset(db: AsyncSession, email: str, otp: str) -> str | None:
    from app.models.otp import EmailOTP

    result = await db.execute(
        select(EmailOTP).where(and_(
            EmailOTP.email == email,
            EmailOTP.otp == otp,
            EmailOTP.purpose == "reset_password",
            EmailOTP.used == False,
            EmailOTP.expires_at > datetime.now(timezone.utc),
        ))
    )
    record = result.scalar_one_or_none()
    if not record:
        return None
    token = generate_reset_token()
    record.reset_token = token
    record.used = True
    return token


async def get_email_by_reset_token(db: AsyncSession, token: str) -> str | None:
    from app.models.otp import EmailOTP
    result = await db.execute(select(EmailOTP).where(EmailOTP.reset_token == token))
    record = result.scalar_one_or_none()
    return record.email if record else None
