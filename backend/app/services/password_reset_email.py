import html
import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_password_reset_email(email: str, full_name: str, token: str) -> None:
    settings = get_settings()
    if not settings.password_reset_email_configured:
        logger.error("Password reset email requested but SMTP is not configured")
        return

    reset_url = f"{settings.frontend_public_url.rstrip('/')}?{urlencode({'reset_token': token})}"
    minutes = settings.password_reset_expire_minutes
    message = EmailMessage()
    message["Subject"] = "Reset your CAMPUSINTEL password"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = email
    message.set_content(
        f"Hello {full_name},\n\n"
        f"A password reset was requested for your CAMPUSINTEL account. Use this link within {minutes} minutes:\n\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this message. Your password will not change unless the link is used.\n"
    )
    message.add_alternative(
        "<p>Hello " + html.escape(full_name) + ",</p>"
        "<p>A password reset was requested for your CAMPUSINTEL account. The link expires in "
        + str(minutes)
        + " minutes.</p><p><a href=\""
        + html.escape(reset_url, quote=True)
        + "\">Reset password</a></p><p>If you did not request this, ignore this message. Your password will not change unless the link is used.</p>",
        subtype="html",
    )

    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        if settings.smtp_starttls and not settings.smtp_use_ssl:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
