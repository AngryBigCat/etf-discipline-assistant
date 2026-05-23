from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

from src.notifications.config import EMAIL_SUBJECT_PREFIX
from src.notifications.models import EmailSendResult


def _build_subject(subject: str) -> str:
    if subject.startswith(EMAIL_SUBJECT_PREFIX):
        return subject
    return f"{EMAIL_SUBJECT_PREFIX} {subject}"


def _validate_settings(settings: dict[str, Any], recipients: list[str]) -> str | None:
    if not settings.get("smtp_host"):
        return "SMTP 主机未配置"
    if not settings.get("email_from"):
        return "发件人未配置"
    if not recipients:
        return "收件人未配置"
    return None


def send_email(
    subject: str,
    body: str,
    recipients: list[str],
    settings: dict[str, Any],
) -> EmailSendResult:
    validation_error = _validate_settings(settings, recipients)
    if validation_error:
        return EmailSendResult(success=False, message=validation_error, error=validation_error)

    message = EmailMessage()
    message["Subject"] = _build_subject(subject)
    message["From"] = settings["email_from"]
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    host = settings["smtp_host"]
    port = int(settings.get("smtp_port") or 587)
    timeout = int(settings.get("timeout") or 30)
    username = settings.get("smtp_username") or ""
    password = settings.get("smtp_password") or ""
    use_ssl = bool(settings.get("smtp_use_ssl"))
    use_tls = bool(settings.get("smtp_use_tls"))

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
        with server:
            if use_tls and not use_ssl:
                server.starttls()
            if username:
                server.login(username, password)
            server.send_message(message)
    except Exception as exc:
        return EmailSendResult(
            success=False,
            message="邮件发送失败",
            error=str(exc),
        )

    return EmailSendResult(success=True, message="邮件发送成功")
