from __future__ import annotations

import os
from typing import Any

EMAIL_SUBJECT_PREFIX = "[ETF纪律助手]"


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_email_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class EmailSettingsView(dict[str, Any]):
    """Settings dict that hides SMTP password in repr/str."""

    def __repr__(self) -> str:
        safe = {key: ("***" if key == "smtp_password" and value else value) for key, value in self.items()}
        return f"EmailSettingsView({safe!r})"


def get_email_settings() -> EmailSettingsView:
    return EmailSettingsView(
        {
            "enabled": _parse_bool(os.getenv("EMAIL_ENABLED"), default=False),
            "smtp_host": (os.getenv("EMAIL_SMTP_HOST") or "").strip(),
            "smtp_port": int(os.getenv("EMAIL_SMTP_PORT") or 587),
            "smtp_username": (os.getenv("EMAIL_SMTP_USERNAME") or "").strip(),
            "smtp_password": os.getenv("EMAIL_SMTP_PASSWORD") or "",
            "smtp_use_tls": _parse_bool(os.getenv("EMAIL_SMTP_USE_TLS"), default=True),
            "smtp_use_ssl": _parse_bool(os.getenv("EMAIL_SMTP_USE_SSL"), default=False),
            "email_from": (os.getenv("EMAIL_FROM") or "").strip(),
            "email_to": _parse_email_list(os.getenv("EMAIL_TO")),
            "timeout": int(os.getenv("EMAIL_TIMEOUT") or 30),
            "notify_on_scheduler_failure": _parse_bool(
                os.getenv("NOTIFY_ON_SCHEDULER_FAILURE"),
                default=True,
            ),
            "notify_on_scheduler_success": _parse_bool(
                os.getenv("NOTIFY_ON_SCHEDULER_SUCCESS"),
                default=False,
            ),
            "notify_on_high_priority_tasks": _parse_bool(
                os.getenv("NOTIFY_ON_HIGH_PRIORITY_TASKS"),
                default=True,
            ),
            "notify_on_portfolio_risk": _parse_bool(
                os.getenv("NOTIFY_ON_PORTFOLIO_RISK"),
                default=True,
            ),
            "notify_on_daily_pipeline_done": _parse_bool(
                os.getenv("NOTIFY_ON_DAILY_PIPELINE_DONE"),
                default=False,
            ),
        }
    )


def mask_email(email: str) -> str:
    value = email.strip()
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def mask_recipients(recipients: list[str]) -> str:
    if not recipients:
        return "—"
    return ", ".join(mask_email(item) for item in recipients)


def format_email_settings_display() -> dict[str, str]:
    settings = get_email_settings()
    return {
        "enabled": "启用" if settings["enabled"] else "未启用",
        "smtp_host": "已配置" if settings["smtp_host"] else "未配置",
        "smtp_username": "已配置" if settings["smtp_username"] else "未配置",
        "smtp_password": "已配置" if settings["smtp_password"] else "未配置",
        "email_from": "已配置" if settings["email_from"] else "未配置",
        "email_to": mask_recipients(settings["email_to"])
        if settings["email_to"]
        else "未配置",
        "notify_on_scheduler_failure": "启用"
        if settings["notify_on_scheduler_failure"]
        else "未启用",
        "notify_on_scheduler_success": "启用"
        if settings["notify_on_scheduler_success"]
        else "未启用",
        "notify_on_high_priority_tasks": "启用"
        if settings["notify_on_high_priority_tasks"]
        else "未启用",
        "notify_on_portfolio_risk": "启用" if settings["notify_on_portfolio_risk"] else "未启用",
        "notify_on_daily_pipeline_done": "启用"
        if settings["notify_on_daily_pipeline_done"]
        else "未启用",
    }
