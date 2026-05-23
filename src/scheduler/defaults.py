from __future__ import annotations

from typing import Any

from src.scheduler.models import JOB_TYPE_DAILY_PIPELINE, JOB_TYPE_WEEKLY_PIPELINE

DEFAULT_SCHEDULER_JOBS: list[dict[str, Any]] = [
    {
        "job_key": "daily_after_close",
        "name": "每日收盘后流程",
        "description": "收盘后更新行情、生成策略信号、刷新任务中心、生成日报与 AI 日复盘。",
        "enabled": 1,
        "cron_expr": "30 16 * * mon-fri",
        "timezone": "Asia/Shanghai",
        "job_type": JOB_TYPE_DAILY_PIPELINE,
        "params_json": None,
        "max_instances": 1,
        "coalesce": 1,
        "misfire_grace_time": 3600,
    },
    {
        "job_key": "weekly_review",
        "name": "每周复盘流程",
        "description": "生成周报、AI 周复盘，并刷新任务中心。",
        "enabled": 1,
        "cron_expr": "30 17 * * fri",
        "timezone": "Asia/Shanghai",
        "job_type": JOB_TYPE_WEEKLY_PIPELINE,
        "params_json": None,
        "max_instances": 1,
        "coalesce": 1,
        "misfire_grace_time": 3600,
    },
]
