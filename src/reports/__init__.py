"""Template-based daily and weekly report generation."""

from src.reports.daily_report import (
    build_and_save_daily_report,
    collect_daily_context,
    generate_daily_report_text,
    save_daily_report,
)
from src.reports.weekly_report import (
    build_and_save_weekly_report,
    collect_weekly_context,
    generate_weekly_report_text,
    save_weekly_report,
)

__all__ = [
    "build_and_save_daily_report",
    "build_and_save_weekly_report",
    "collect_daily_context",
    "collect_weekly_context",
    "generate_daily_report_text",
    "generate_weekly_report_text",
    "save_daily_report",
    "save_weekly_report",
]
