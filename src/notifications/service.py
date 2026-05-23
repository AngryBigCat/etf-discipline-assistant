from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from src.notifications.config import get_email_settings, mask_recipients
from src.notifications.email_client import send_email
from src.notifications.models import (
    CHANNEL_EMAIL,
    EVENT_DAILY_PIPELINE_DONE,
    EVENT_HIGH_PRIORITY_TASKS,
    EVENT_PORTFOLIO_RISK,
    EVENT_SCHEDULER_FAILURE,
    EVENT_SCHEDULER_SUCCESS,
    LEVEL_ERROR,
    LEVEL_INFO,
    LEVEL_WARNING,
    NotificationResult,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
)
from src.notifications.repository import (
    has_success_notification,
    save_notification_log,
)
from src.notifications.templates import (
    build_daily_pipeline_done_email,
    build_high_priority_tasks_email,
    build_portfolio_risk_email,
    build_scheduler_failure_email,
    build_scheduler_success_email,
)
from src.workflows.daily_workflow import WorkflowResult


def _now_str() -> str:
    return datetime.now().isoformat(timespec="seconds")


def send_notification(
    conn,
    *,
    event_type: str,
    level: str,
    title: str,
    body: str,
    dedupe_key: str | None = None,
    source_type: str | None = None,
    source_key: str | None = None,
) -> NotificationResult:
    settings = get_email_settings()
    recipient_masked = mask_recipients(settings["email_to"])

    if not settings["enabled"]:
        save_notification_log(
            conn,
            {
                "channel": CHANNEL_EMAIL,
                "event_type": event_type,
                "level": level,
                "title": title,
                "body_preview": body,
                "recipient_masked": recipient_masked,
                "status": STATUS_SKIPPED,
                "dedupe_key": dedupe_key,
                "source_type": source_type,
                "source_key": source_key,
                "error_message": "邮件通知未启用",
                "sent_at": None,
            },
        )
        return NotificationResult(
            success=True,
            status=STATUS_SKIPPED,
            message="邮件通知未启用，已跳过",
        )

    if dedupe_key and has_success_notification(conn, dedupe_key, channel=CHANNEL_EMAIL):
        save_notification_log(
            conn,
            {
                "channel": CHANNEL_EMAIL,
                "event_type": event_type,
                "level": level,
                "title": title,
                "body_preview": body,
                "recipient_masked": recipient_masked,
                "status": STATUS_SKIPPED,
                "dedupe_key": dedupe_key,
                "source_type": source_type,
                "source_key": source_key,
                "error_message": "重复通知已跳过",
                "sent_at": None,
            },
        )
        return NotificationResult(
            success=True,
            status=STATUS_SKIPPED,
            message="重复通知已跳过",
        )

    try:
        send_result = send_email(title, body, settings["email_to"], settings)
    except Exception as exc:
        logger.warning("邮件发送异常：{}", exc)
        save_notification_log(
            conn,
            {
                "channel": CHANNEL_EMAIL,
                "event_type": event_type,
                "level": level,
                "title": title,
                "body_preview": body,
                "recipient_masked": recipient_masked,
                "status": STATUS_FAILED,
                "dedupe_key": dedupe_key,
                "source_type": source_type,
                "source_key": source_key,
                "error_message": str(exc),
                "sent_at": None,
            },
        )
        return NotificationResult(
            success=False,
            status=STATUS_FAILED,
            message="邮件发送异常",
            error=str(exc),
        )

    if send_result.success:
        save_notification_log(
            conn,
            {
                "channel": CHANNEL_EMAIL,
                "event_type": event_type,
                "level": level,
                "title": title,
                "body_preview": body,
                "recipient_masked": recipient_masked,
                "status": STATUS_SUCCESS,
                "dedupe_key": dedupe_key,
                "source_type": source_type,
                "source_key": source_key,
                "error_message": None,
                "sent_at": _now_str(),
            },
        )
        return NotificationResult(
            success=True,
            status=STATUS_SUCCESS,
            message=send_result.message,
        )

    save_notification_log(
        conn,
        {
            "channel": CHANNEL_EMAIL,
            "event_type": event_type,
            "level": level,
            "title": title,
            "body_preview": body,
            "recipient_masked": recipient_masked,
            "status": STATUS_FAILED,
            "dedupe_key": dedupe_key,
            "source_type": source_type,
            "source_key": source_key,
            "error_message": send_result.error,
            "sent_at": None,
        },
    )
    return NotificationResult(
        success=False,
        status=STATUS_FAILED,
        message=send_result.message,
        error=send_result.error,
    )


def _list_pending_high_priority_tasks(conn, task_date: str) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT *
        FROM task_item
        WHERE task_date = ? AND status = 'pending' AND priority = 'high'
        ORDER BY id
        """,
        (task_date,),
    )
    return [dict(row) for row in cur.fetchall()]


def _list_pending_portfolio_risk_tasks(conn, task_date: str) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT *
        FROM task_item
        WHERE task_date = ?
          AND status = 'pending'
          AND category = 'risk'
          AND priority = 'high'
        ORDER BY id
        """,
        (task_date,),
    )
    return [dict(row) for row in cur.fetchall()]


def send_scheduler_job_notifications(
    conn,
    job: dict[str, Any],
    result: WorkflowResult,
    *,
    scheduled_time: str,
    job_success: bool,
) -> list[NotificationResult]:
    settings = get_email_settings()
    outcomes: list[NotificationResult] = []
    job_key = str(job.get("job_key") or "")

    if not job_success and settings["notify_on_scheduler_failure"]:
        subject, body = build_scheduler_failure_email(job, result, scheduled_time)
        outcomes.append(
            send_notification(
                conn,
                event_type=EVENT_SCHEDULER_FAILURE,
                level=LEVEL_ERROR,
                title=subject,
                body=body,
                dedupe_key=f"scheduler_failure:{job_key}:{scheduled_time}",
                source_type="scheduler_job",
                source_key=job_key,
            )
        )
    elif job_success and settings["notify_on_scheduler_success"]:
        subject, body = build_scheduler_success_email(job, result, scheduled_time)
        outcomes.append(
            send_notification(
                conn,
                event_type=EVENT_SCHEDULER_SUCCESS,
                level=LEVEL_INFO,
                title=subject,
                body=body,
                dedupe_key=f"scheduler_success:{job_key}:{scheduled_time}",
                source_type="scheduler_job",
                source_key=job_key,
            )
        )

    for outcome in outcomes:
        if outcome.status == STATUS_FAILED:
            logger.warning(
                "定时任务通知发送失败：{} {}",
                job_key,
                outcome.error or outcome.message,
            )
    return outcomes


def send_daily_pipeline_notifications(
    conn,
    run_date: str,
    pipeline_result: WorkflowResult,
) -> list[dict[str, Any]]:
    settings = get_email_settings()
    summaries: list[dict[str, Any]] = []

    def _record(name: str, outcome: NotificationResult) -> None:
        if outcome.status == STATUS_FAILED:
            logger.warning("每日流程通知发送失败：{} {}", name, outcome.error or outcome.message)
        summaries.append(
            {
                "notification": name,
                "status": outcome.status,
                "message": outcome.message,
                "error": outcome.error,
            }
        )

    if settings["notify_on_high_priority_tasks"]:
        tasks = _list_pending_high_priority_tasks(conn, run_date)
        if tasks:
            subject, body = build_high_priority_tasks_email(tasks, run_date)
            outcome = send_notification(
                conn,
                event_type=EVENT_HIGH_PRIORITY_TASKS,
                level=LEVEL_WARNING,
                title=subject,
                body=body,
                dedupe_key=f"high_priority_tasks:{run_date}",
                source_type="task_item",
                source_key=run_date,
            )
            _record("high_priority_tasks", outcome)

    if settings["notify_on_portfolio_risk"]:
        alerts = _list_pending_portfolio_risk_tasks(conn, run_date)
        if alerts:
            subject, body = build_portfolio_risk_email(alerts, run_date)
            outcome = send_notification(
                conn,
                event_type=EVENT_PORTFOLIO_RISK,
                level=LEVEL_WARNING,
                title=subject,
                body=body,
                dedupe_key=f"portfolio_risk:{run_date}",
                source_type="task_item",
                source_key=run_date,
            )
            _record("portfolio_risk", outcome)

    if settings["notify_on_daily_pipeline_done"]:
        subject, body = build_daily_pipeline_done_email(pipeline_result, run_date)
        outcome = send_notification(
            conn,
            event_type=EVENT_DAILY_PIPELINE_DONE,
            level=LEVEL_INFO,
            title=subject,
            body=body,
            dedupe_key=f"daily_pipeline_done:{run_date}",
            source_type="daily_pipeline",
            source_key=run_date,
        )
        _record("daily_pipeline_done", outcome)

    return summaries
