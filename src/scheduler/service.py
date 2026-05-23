from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.scheduler.models import SchedulerJob
from src.scheduler.repository import list_scheduler_jobs
from src.scheduler.runner import run_scheduler_job


def parse_cron_expr(cron_expr: str) -> dict[str, str]:
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"cron 表达式必须是 5 段，当前为 {len(parts)} 段：{cron_expr}")
    minute, hour, day, month, day_of_week = parts
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }


def build_cron_trigger(job: SchedulerJob | dict[str, Any]) -> CronTrigger:
    if isinstance(job, SchedulerJob):
        cron_expr = job.cron_expr
        timezone = job.timezone
        job_key = job.job_key
    else:
        cron_expr = str(job["cron_expr"])
        timezone = str(job.get("timezone") or "Asia/Shanghai")
        job_key = str(job["job_key"])

    fields = parse_cron_expr(cron_expr)
    try:
        tz = ZoneInfo(timezone)
    except Exception as exc:
        raise ValueError(f"任务 {job_key} 的时区无效：{timezone}") from exc

    return CronTrigger(
        minute=fields["minute"],
        hour=fields["hour"],
        day=fields["day"],
        month=fields["month"],
        day_of_week=fields["day_of_week"],
        timezone=tz,
    )


def _scheduled_job_wrapper(job_key: str) -> None:
    scheduled_time = datetime.now().isoformat(timespec="seconds")
    result = run_scheduler_job(job_key, scheduled_time=scheduled_time)
    if result.success:
        logger.info("[{}] {}", job_key, result.message)
    else:
        logger.warning("[{}] {}", job_key, result.message)
        if result.detail:
            logger.warning(result.detail)


def create_blocking_scheduler(conn) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    jobs = list_scheduler_jobs(conn, enabled_only=True)
    for job_row in jobs:
        job = SchedulerJob.from_row(job_row)
        trigger = build_cron_trigger(job)
        scheduler.add_job(
            _scheduled_job_wrapper,
            trigger=trigger,
            id=job.job_key,
            name=job.name,
            args=[job.job_key],
            max_instances=job.max_instances,
            coalesce=bool(job.coalesce),
            misfire_grace_time=job.misfire_grace_time,
            replace_existing=True,
        )
        next_run = trigger.get_next_fire_time(None, datetime.now(tz=trigger.timezone))
        logger.info(
            "已注册任务：{} ({}) cron={} 下次运行={}",
            job.name,
            job.job_key,
            job.cron_expr,
            next_run,
        )
    logger.info("共加载 {} 个启用任务", len(jobs))
    return scheduler
