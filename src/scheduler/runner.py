from __future__ import annotations

import traceback
from datetime import datetime

from loguru import logger

from src.config.settings import load_settings
from src.db.connection import db_session
from src.notifications.service import send_scheduler_job_notifications
from src.scheduler.models import (
    JOB_TYPE_DAILY_PIPELINE,
    JOB_TYPE_WEEKLY_PIPELINE,
    RUN_STATUS_FAILED,
    RUN_STATUS_RUNNING,
    RUN_STATUS_SKIPPED,
    RUN_STATUS_SUCCESS,
)
from src.scheduler.repository import (
    ensure_default_scheduler_jobs,
    get_scheduler_job,
    save_scheduler_run_log,
    update_scheduler_run_log,
)
from src.workflows.daily_workflow import WorkflowResult
from src.workflows.pipelines import run_daily_pipeline, run_weekly_pipeline


def _now_str() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _run_pipeline(conn, settings: dict, job_type: str) -> WorkflowResult:
    if job_type == JOB_TYPE_DAILY_PIPELINE:
        return run_daily_pipeline(conn, settings)
    if job_type == JOB_TYPE_WEEKLY_PIPELINE:
        return run_weekly_pipeline(conn, settings)
    return WorkflowResult(success=False, message=f"未知任务类型：{job_type}")


def run_scheduler_job(
    job_key: str,
    *,
    scheduled_time: str | None = None,
) -> WorkflowResult:
    settings = load_settings()
    scheduled_time = scheduled_time or _now_str()

    try:
        with db_session() as conn:
            ensure_default_scheduler_jobs(conn)
            job = get_scheduler_job(conn, job_key)
            if job is None:
                return WorkflowResult(success=False, message=f"任务不存在：{job_key}")

            if not bool(job.get("enabled")):
                save_scheduler_run_log(
                    conn,
                    {
                        "job_key": job_key,
                        "scheduled_time": scheduled_time,
                        "started_at": _now_str(),
                        "finished_at": _now_str(),
                        "status": RUN_STATUS_SKIPPED,
                        "message": "任务已停用，跳过执行",
                        "detail": None,
                    },
                )
                return WorkflowResult(
                    success=True,
                    message="任务已停用，跳过执行",
                    detail=RUN_STATUS_SKIPPED,
                )

            log_id = save_scheduler_run_log(
                conn,
                {
                    "job_key": job_key,
                    "scheduled_time": scheduled_time,
                    "started_at": _now_str(),
                    "finished_at": None,
                    "status": RUN_STATUS_RUNNING,
                    "message": "任务开始执行",
                    "detail": None,
                },
            )

            try:
                result = _run_pipeline(conn, settings, str(job["job_type"]))
            except Exception as exc:
                detail = traceback.format_exc()
                failure_result = WorkflowResult(
                    success=False,
                    message="任务执行异常",
                    detail=str(exc),
                )
                update_scheduler_run_log(
                    conn,
                    log_id,
                    {
                        "finished_at": _now_str(),
                        "status": RUN_STATUS_FAILED,
                        "message": failure_result.message,
                        "detail": detail,
                    },
                )
                try:
                    send_scheduler_job_notifications(
                        conn,
                        job,
                        failure_result,
                        scheduled_time=scheduled_time,
                        job_success=False,
                    )
                except Exception as notify_exc:
                    logger.warning("定时任务失败通知发送异常：{}", notify_exc)
                logger.exception("定时任务 {} 执行异常", job_key)
                return failure_result

            status = RUN_STATUS_SUCCESS if result.success else RUN_STATUS_FAILED
            update_scheduler_run_log(
                conn,
                log_id,
                {
                    "finished_at": _now_str(),
                    "status": status,
                    "message": result.message,
                    "detail": result.detail,
                },
            )
            try:
                send_scheduler_job_notifications(
                    conn,
                    job,
                    result,
                    scheduled_time=scheduled_time,
                    job_success=result.success,
                )
            except Exception as notify_exc:
                logger.warning("定时任务通知发送异常：{}", notify_exc)
            return result
    except Exception as exc:
        logger.exception("定时任务 {} 启动失败", job_key)
        return WorkflowResult(
            success=False,
            message="定时任务启动失败",
            detail=str(exc),
        )
