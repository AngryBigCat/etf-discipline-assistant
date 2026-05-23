from __future__ import annotations

from dataclasses import dataclass

CHANNEL_EMAIL = "email"

STATUS_SKIPPED = "skipped"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

LEVEL_INFO = "info"
LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"

EVENT_TEST_EMAIL = "test_email"
EVENT_SCHEDULER_FAILURE = "scheduler_failure"
EVENT_SCHEDULER_SUCCESS = "scheduler_success"
EVENT_HIGH_PRIORITY_TASKS = "high_priority_tasks"
EVENT_PORTFOLIO_RISK = "portfolio_risk"
EVENT_DAILY_PIPELINE_DONE = "daily_pipeline_done"


@dataclass
class EmailSendResult:
    success: bool
    message: str
    error: str | None = None


@dataclass
class NotificationResult:
    success: bool
    status: str
    message: str
    error: str | None = None
