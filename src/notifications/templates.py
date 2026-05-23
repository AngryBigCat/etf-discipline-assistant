from __future__ import annotations

from typing import Any

from src.notifications.config import EMAIL_SUBJECT_PREFIX
from src.workflows.daily_workflow import WorkflowResult

DISCLAIMER = (
    "本邮件仅用于流程提醒，不构成投资建议，不会自动交易。"
    "请打开系统查看详情并人工确认。"
)


def build_scheduler_failure_email(
    job: dict[str, Any],
    result: WorkflowResult,
    scheduled_time: str,
) -> tuple[str, str]:
    job_name = job.get("name") or job.get("job_key") or "未知任务"
    subject = f"定时任务失败：{job_name}"
    body = "\n".join(
        [
            DISCLAIMER,
            "",
            f"任务名称：{job_name}",
            f"任务标识：{job.get('job_key') or '—'}",
            f"计划时间：{scheduled_time}",
            f"执行状态：失败",
            f"失败原因：{result.message}",
            f"详情：{result.detail or '—'}",
        ]
    )
    return subject, body


def build_scheduler_success_email(
    job: dict[str, Any],
    result: WorkflowResult,
    scheduled_time: str,
) -> tuple[str, str]:
    job_name = job.get("name") or job.get("job_key") or "未知任务"
    subject = f"定时任务成功：{job_name}"
    body = "\n".join(
        [
            DISCLAIMER,
            "",
            f"任务名称：{job_name}",
            f"任务标识：{job.get('job_key') or '—'}",
            f"计划时间：{scheduled_time}",
            f"执行状态：成功",
            f"结果说明：{result.message}",
        ]
    )
    return subject, body


def build_high_priority_tasks_email(
    tasks: list[dict[str, Any]],
    task_date: str,
) -> tuple[str, str]:
    subject = f"高优先级任务提醒：{task_date}"
    lines = [
        DISCLAIMER,
        "",
        f"日期：{task_date}",
        f"待处理高优先级任务：{len(tasks)} 条",
        "",
    ]
    for task in tasks[:20]:
        lines.append(f"- {task.get('title') or '未命名任务'}")
    if len(tasks) > 20:
        lines.append(f"... 另有 {len(tasks) - 20} 条未列出")
    lines.append("")
    lines.append("请打开系统任务中心查看并人工处理。")
    return subject, "\n".join(lines)


def build_portfolio_risk_email(
    alerts: list[dict[str, Any]],
    task_date: str,
) -> tuple[str, str]:
    subject = "仓位风险提醒：请人工确认"
    lines = [
        DISCLAIMER,
        "",
        f"日期：{task_date}",
        f"待处理仓位风险提醒：{len(alerts)} 条",
        "",
    ]
    for alert in alerts[:20]:
        lines.append(f"- {alert.get('title') or '未命名风险提醒'}")
    if len(alerts) > 20:
        lines.append(f"... 另有 {len(alerts) - 20} 条未列出")
    lines.append("")
    lines.append("请打开系统查看仓位与风险详情，并人工确认。")
    return subject, "\n".join(lines)


def build_daily_pipeline_done_email(
    result: WorkflowResult,
    run_date: str,
) -> tuple[str, str]:
    subject = f"每日流程完成：{run_date}"
    body = "\n".join(
        [
            DISCLAIMER,
            "",
            f"日期：{run_date}",
            f"流程状态：成功",
            f"结果说明：{result.message}",
        ]
    )
    return subject, body


def build_test_email_body() -> str:
    return "\n".join(
        [
            "这是一封测试邮件，仅用于验证邮件通知配置。",
            "",
            DISCLAIMER,
        ]
    )


def format_subject_for_display(subject: str) -> str:
    if subject.startswith(EMAIL_SUBJECT_PREFIX):
        return subject
    return f"{EMAIL_SUBJECT_PREFIX} {subject}"
