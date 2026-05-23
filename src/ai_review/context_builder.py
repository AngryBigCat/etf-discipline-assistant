from __future__ import annotations

from typing import Any

from src.config.settings import get_watch_only_assets
from src.db.repository import (
    get_daily_report_by_date,
    get_latest_strategy_signals,
    get_portfolio_overview,
    get_trade_logs,
    get_weekly_report,
)
from src.reports.daily_report import bucket_signals, summarize_day_trades

DAILY_REPORT_MISSING = "暂无日报，请先在报告复盘页面生成日报。"
WEEKLY_REPORT_MISSING = "暂无周报，请先在报告复盘页面生成周报。"


def _sanitize_account(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_position": float(account.get("total_position") or 0),
        "cash_position": float(account.get("cash_position") or 0),
        "valid": bool(account.get("valid")),
    }


def _sanitize_alerts(overview: dict[str, Any]) -> list[str]:
    return [str(alert.get("message") or "") for alert in overview.get("alerts", [])]


def build_daily_review_context(
    conn,
    settings: dict[str, Any],
    target_date: str,
) -> dict[str, Any]:
    daily_report = get_daily_report_by_date(conn, target_date)
    if daily_report is None:
        return {
            "missing": True,
            "message": DAILY_REPORT_MISSING,
            "target_date": target_date,
        }

    overview = get_portfolio_overview(conn, settings)
    signals = [dict(row) for row in get_latest_strategy_signals(conn)]
    watch_only = get_watch_only_assets(settings)
    trade_rows = get_trade_logs(conn, start_date=target_date, end_date=target_date)
    day_trade_stats = summarize_day_trades(trade_rows)

    return {
        "missing": False,
        "review_type": "daily",
        "target_date": target_date,
        "daily_report": dict(daily_report),
        "overview_account": _sanitize_account(overview.get("account", {})),
        "alerts": _sanitize_alerts(overview),
        "signals_bucketed": bucket_signals(signals),
        "day_trade_stats": day_trade_stats,
        "watch_only": [{"symbol": a["symbol"], "name": a.get("name", a["symbol"])} for a in watch_only],
    }


def build_weekly_review_context(
    conn,
    settings: dict[str, Any],
    week_start: str,
    week_end: str,
) -> dict[str, Any]:
    weekly_report = get_weekly_report(conn, week_start, week_end)
    if weekly_report is None:
        return {
            "missing": True,
            "message": WEEKLY_REPORT_MISSING,
            "week_start": week_start,
            "week_end": week_end,
        }

    from src.trading.trade_log import get_trade_summary

    overview = get_portfolio_overview(conn, settings)
    signals = [dict(row) for row in get_latest_strategy_signals(conn)]
    watch_only = get_watch_only_assets(settings)
    trade_summary = get_trade_summary(conn, start_date=week_start, end_date=week_end)

    return {
        "missing": False,
        "review_type": "weekly",
        "week_start": week_start,
        "week_end": week_end,
        "weekly_report": dict(weekly_report),
        "overview_account": _sanitize_account(overview.get("account", {})),
        "alerts": _sanitize_alerts(overview),
        "signals_bucketed": bucket_signals(signals),
        "trade_summary": trade_summary,
        "watch_only": [{"symbol": a["symbol"], "name": a.get("name", a["symbol"])} for a in watch_only],
    }
