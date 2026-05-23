from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.tasks.rules import (
    TASK_CHECK_INDICATORS,
    TASK_CHECK_PORTFOLIO_DEVIATION,
    TASK_CHECK_PORTFOLIO_RISK,
    TASK_EXCEED_MAX_POSITION,
    TASK_GENERATE_AI_DAILY_REVIEW,
    TASK_GENERATE_AI_WEEKLY_REVIEW,
    TASK_GENERATE_DAILY_REPORT,
    TASK_GENERATE_STRATEGY_SIGNAL,
    TASK_GENERATE_WEEKLY_REPORT,
    TASK_INPUT_HOLDING_SNAPSHOT,
    TASK_MISSING_HOLDING_SNAPSHOT,
    TASK_NON_RULE_BASED_TRADE,
    TASK_OVERWEIGHT_POSITION,
    TASK_RECORD_TRADE_LOG,
    TASK_REVIEW_STRATEGY_SIGNAL,
    TASK_UPDATE_MARKET_DATA,
    TASK_WATCH_ONLY_OVERWEIGHT,
)
from src.workflows.daily_workflow import (
    run_generate_ai_daily_review,
    run_generate_ai_weekly_review,
    run_generate_daily_report,
    run_generate_signals,
    run_generate_weekly_report,
    run_market_update,
)

EXECUTABLE_TASK_TYPES = {
    TASK_UPDATE_MARKET_DATA,
    TASK_GENERATE_STRATEGY_SIGNAL,
    TASK_GENERATE_DAILY_REPORT,
    TASK_GENERATE_WEEKLY_REPORT,
    TASK_GENERATE_AI_DAILY_REVIEW,
    TASK_GENERATE_AI_WEEKLY_REVIEW,
}

NON_EXECUTABLE_GUIDANCE: dict[str, str] = {
    TASK_INPUT_HOLDING_SNAPSHOT: "请前往「持仓录入」页面手动录入快照。",
    TASK_MISSING_HOLDING_SNAPSHOT: "请前往「持仓录入」页面手动录入快照。",
    TASK_REVIEW_STRATEGY_SIGNAL: "请前往「策略信号」页面人工确认，不支持自动审核。",
    TASK_RECORD_TRADE_LOG: "如有实际交易，请前往「交易日志」页面手动记录。",
    TASK_CHECK_PORTFOLIO_RISK: "请前往「仓位管理」页面查看风险，不会自动调整仓位。",
    TASK_EXCEED_MAX_POSITION: "请前往「仓位管理」页面查看风险，不会自动调整仓位。",
    TASK_OVERWEIGHT_POSITION: "请前往「仓位管理」页面查看风险，不会自动调整仓位。",
    TASK_WATCH_ONLY_OVERWEIGHT: "请前往「仓位管理」页面查看风险，不会自动调整仓位。",
    TASK_CHECK_PORTFOLIO_DEVIATION: "请前往「仓位管理」或「回测分析」页面查看组合偏离。",
    TASK_NON_RULE_BASED_TRADE: "请前往「交易日志」页面回顾交易纪律，不会自动修改记录。",
    TASK_CHECK_INDICATORS: "请先执行任务「更新行情数据」，指标会随行情更新一并计算。",
}


@dataclass
class TaskActionResult:
    success: bool
    message: str
    detail: str | None = None
    should_mark_done: bool = False


def is_executable_task(task_type: str) -> bool:
    return task_type in EXECUTABLE_TASK_TYPES


def get_task_guidance(task_type: str) -> str | None:
    return NON_EXECUTABLE_GUIDANCE.get(task_type)


def _rolling_week(task_date: str) -> tuple[str, str]:
    end_dt = datetime.strptime(task_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=6)
    return start_dt.strftime("%Y-%m-%d"), task_date


def _parse_week_range(task: dict[str, Any]) -> tuple[str, str]:
    source_key = str(task.get("source_key") or "")
    if "_" in source_key:
        week_start, week_end = source_key.split("_", 1)
        return week_start, week_end
    return _rolling_week(str(task["task_date"]))


def execute_task_action(conn, settings: dict[str, Any], task: dict[str, Any]) -> TaskActionResult:
    task_type = str(task.get("task_type") or "")
    if not is_executable_task(task_type):
        guidance = get_task_guidance(task_type) or "该任务需人工处理，不支持一键执行。"
        return TaskActionResult(success=False, message=guidance, should_mark_done=False)

    task_date = str(task.get("task_date") or "")

    try:
        if task_type == TASK_UPDATE_MARKET_DATA:
            workflow_result = run_market_update(conn, settings)
        elif task_type == TASK_GENERATE_STRATEGY_SIGNAL:
            workflow_result = run_generate_signals(conn, settings)
        elif task_type == TASK_GENERATE_DAILY_REPORT:
            report_date = str(task.get("source_key") or task_date)
            workflow_result = run_generate_daily_report(conn, settings, report_date)
        elif task_type == TASK_GENERATE_WEEKLY_REPORT:
            week_start, week_end = _parse_week_range(task)
            workflow_result = run_generate_weekly_report(conn, settings, week_start, week_end)
        elif task_type == TASK_GENERATE_AI_DAILY_REVIEW:
            review_date = str(task.get("source_key") or task_date)
            workflow_result = run_generate_ai_daily_review(conn, settings, review_date)
        elif task_type == TASK_GENERATE_AI_WEEKLY_REVIEW:
            week_start, week_end = _parse_week_range(task)
            workflow_result = run_generate_ai_weekly_review(conn, settings, week_start, week_end)
        else:
            return TaskActionResult(success=False, message="未知任务类型，无法执行。", should_mark_done=False)
    except Exception as exc:
        return TaskActionResult(
            success=False,
            message="任务执行失败",
            detail=str(exc),
            should_mark_done=False,
        )

    return TaskActionResult(
        success=workflow_result.success,
        message=workflow_result.message,
        detail=workflow_result.detail,
        should_mark_done=workflow_result.success,
    )
