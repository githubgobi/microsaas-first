"""
Async email sending via SMTP.

When SMTP_HOST is empty (default in dev/test), the function logs the
verification URL to stdout instead of sending, so you can copy-paste it
without needing a real mail server.
"""
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import structlog

from app.config import get_settings

logger = structlog.get_logger()


async def send_verification_email(to_email: str, token: str) -> None:
    settings = get_settings()
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"

    if not settings.SMTP_HOST:
        # Dev / test mode — no SMTP configured; log the link so it can be used manually.
        logger.info(
            "verification_email_skipped",
            reason="smtp_not_configured",
            email=to_email,
            verify_url=verify_url,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Verify your {settings.APP_NAME} account"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email

    text_body = (
        f"Welcome to {settings.APP_NAME}!\n\n"
        f"Verify your email address by visiting:\n{verify_url}\n\n"
        "This link expires in 24 hours. "
        "If you did not create an account, you can safely ignore this email."
    )
    html_body = f"""
<p>Welcome to <strong>{settings.APP_NAME}</strong>!</p>
<p><a href="{verify_url}">Click here to verify your email address</a></p>
<p>This link expires in 24 hours.</p>
<p>If you did not create an account, you can safely ignore this email.</p>
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER or None,
        password=settings.SMTP_PASSWORD or None,
        use_tls=settings.SMTP_TLS,
    )
    logger.info("verification_email_sent", email=to_email)


async def send_password_reset_email(to_email: str, token: str) -> None:
    settings = get_settings()
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    if not settings.SMTP_HOST:
        logger.info(
            "password_reset_email_skipped",
            reason="smtp_not_configured",
            email=to_email,
            reset_url=reset_url,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Reset your {settings.APP_NAME} password"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email

    text_body = (
        f"You requested a password reset for your {settings.APP_NAME} account.\n\n"
        f"Reset your password by visiting:\n{reset_url}\n\n"
        "This link expires in 1 hour. "
        "If you did not request a reset, you can safely ignore this email — "
        "your password has not been changed."
    )
    html_body = f"""
<p>You requested a password reset for your <strong>{settings.APP_NAME}</strong> account.</p>
<p><a href="{reset_url}">Click here to reset your password</a></p>
<p>This link expires in 1 hour.</p>
<p>If you did not request a reset, you can safely ignore this email — your password has not been changed.</p>
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER or None,
        password=settings.SMTP_PASSWORD or None,
        use_tls=settings.SMTP_TLS,
    )
    logger.info("password_reset_email_sent", email=to_email)
