from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RUN_STATUS_RUNNING = "running"
RUN_STATUS_SUCCESS = "success"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_SKIPPED = "skipped"

JOB_TYPE_DAILY_PIPELINE = "daily_pipeline"
JOB_TYPE_WEEKLY_PIPELINE = "weekly_pipeline"


@dataclass
class SchedulerJob:
    job_key: str
    name: str
    cron_expr: str
    job_type: str
    enabled: bool = True
    description: str | None = None
    timezone: str = "Asia/Shanghai"
    params_json: str | None = None
    max_instances: int = 1
    coalesce: int = 1
    misfire_grace_time: int = 3600
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row: Any) -> SchedulerJob:
        data = dict(row)
        return cls(
            id=data.get("id"),
            job_key=str(data["job_key"]),
            name=str(data["name"]),
            description=data.get("description"),
            enabled=bool(data.get("enabled", 1)),
            cron_expr=str(data["cron_expr"]),
            timezone=str(data.get("timezone") or "Asia/Shanghai"),
            job_type=str(data["job_type"]),
            params_json=data.get("params_json"),
            max_instances=int(data.get("max_instances") or 1),
            coalesce=int(data.get("coalesce") or 1),
            misfire_grace_time=int(data.get("misfire_grace_time") or 3600),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
