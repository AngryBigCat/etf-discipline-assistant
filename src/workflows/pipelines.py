from __future__ import annotations

import json
from typing import Any, Callable

from src.tasks.generators import _rolling_week
from src.tasks.service import refresh_tasks_for_date
from src.utils.date_utils import today_str
from src.workflows.daily_workflow import (
    WorkflowResult,
    run_generate_ai_daily_review,
    run_generate_ai_weekly_review,
    run_generate_daily_report,
    run_generate_signals,
    run_generate_weekly_report,
    run_market_update,
)


def _run_refresh_tasks(conn, settings: dict[str, Any], run_date: str) -> WorkflowResult:
    try:
        tasks = refresh_tasks_for_date(conn, settings, run_date)
    except Exception as exc:
        return WorkflowResult(success=False, message="任务中心刷新失败", detail=str(exc))
    return WorkflowResult(
        success=True,
        message=f"任务中心已刷新，共 {len(tasks)} 条",
    )


def _serialize_steps(steps: list[dict[str, Any]]) -> str:
    return json.dumps(steps, ensure_ascii=False, indent=2)


def _run_pipeline_steps(
    steps: list[tuple[str, Callable[[], WorkflowResult]]],
    *,
    pipeline_name: str,
) -> WorkflowResult:
    step_results: list[dict[str, Any]] = []
    for step_name, step_fn in steps:
        try:
            result = step_fn()
        except Exception as exc:
            result = WorkflowResult(
                success=False,
                message=f"{step_name} 执行异常",
                detail=str(exc),
            )
        step_results.append(
            {
                "step": step_name,
                "success": result.success,
                "message": result.message,
                "detail": result.detail,
            }
        )
        if not result.success:
            return WorkflowResult(
                success=False,
                message=f"{pipeline_name} 在步骤 {step_name} 失败：{result.message}",
                detail=_serialize_steps(step_results),
            )

    return WorkflowResult(
        success=True,
        message=f"{pipeline_name} 执行完成",
        detail=_serialize_steps(step_results),
    )


def run_daily_pipeline(
    conn,
    settings: dict[str, Any],
    run_date: str | None = None,
) -> WorkflowResult:
    report_date = run_date or today_str()
    steps = [
        ("market_update", lambda: run_market_update(conn, settings)),
        ("generate_signals", lambda: run_generate_signals(conn, settings)),
        ("refresh_tasks", lambda: _run_refresh_tasks(conn, settings, report_date)),
        (
            "daily_report",
            lambda: run_generate_daily_report(conn, settings, report_date),
        ),
        (
            "ai_daily_review",
            lambda: run_generate_ai_daily_review(conn, settings, report_date),
        ),
        (
            "refresh_tasks_final",
            lambda: _run_refresh_tasks(conn, settings, report_date),
        ),
    ]
    return _run_pipeline_steps(steps, pipeline_name="每日收盘后流程")


def run_weekly_pipeline(
    conn,
    settings: dict[str, Any],
    run_date: str | None = None,
) -> WorkflowResult:
    task_date = run_date or today_str()
    week_start, week_end = _rolling_week(task_date)
    steps = [
        (
            "weekly_report",
            lambda: run_generate_weekly_report(conn, settings, week_start, week_end),
        ),
        (
            "ai_weekly_review",
            lambda: run_generate_ai_weekly_review(conn, settings, week_start, week_end),
        ),
        ("refresh_tasks", lambda: _run_refresh_tasks(conn, settings, task_date)),
    ]
    return _run_pipeline_steps(steps, pipeline_name="每周复盘流程")
