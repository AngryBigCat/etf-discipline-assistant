from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.collectors.price_service import CompositeCollector
from src.db.repository import (
    get_daily_prices,
    list_priceable_etfs,
    upsert_daily_prices,
    upsert_indicator_rows,
)
from src.indicators.indicator_service import compute_indicators_for_symbol


@dataclass
class WorkflowResult:
    success: bool
    message: str
    detail: str | None = None


def run_market_update(conn, settings: dict[str, Any] | None = None) -> WorkflowResult:
    _ = settings
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    collector = CompositeCollector()

    etfs = list_priceable_etfs(conn)
    if not etfs:
        return WorkflowResult(success=False, message="未找到可采集 ETF，请先运行 seed_data.py")

    sources: dict[str, str] = {}
    updated_symbols: list[str] = []
    try:
        for etf in etfs:
            symbol = etf["symbol"]
            fund_code = etf["fund_code"]
            result = collector.fetch_history(symbol, fund_code, start_date, end_date)
            upsert_daily_prices(conn, result.df)
            sources[symbol] = result.source
            updated_symbols.append(symbol)

            price_df = get_daily_prices(conn, symbol)
            indicator_rows = compute_indicators_for_symbol(symbol, price_df)
            if indicator_rows:
                upsert_indicator_rows(conn, indicator_rows)
    except Exception as exc:
        return WorkflowResult(
            success=False,
            message="行情更新失败",
            detail=str(exc),
        )

    detail = "、".join(f"{symbol}({source})" for symbol, source in sources.items())
    return WorkflowResult(
        success=True,
        message=f"行情更新完成，共更新 {len(updated_symbols)} 个标的",
        detail=detail or None,
    )


def run_generate_signals(conn, settings: dict[str, Any]) -> WorkflowResult:
    from src.strategy.signal_generator import SnapshotRequiredError, generate_and_save_signals

    try:
        signals, context = generate_and_save_signals(conn, settings)
    except SnapshotRequiredError as exc:
        return WorkflowResult(success=False, message=str(exc))
    except Exception as exc:
        return WorkflowResult(success=False, message="策略信号生成失败", detail=str(exc))

    signal_date = context.get("signal_date") or "—"
    return WorkflowResult(
        success=True,
        message=f"策略信号已生成：{signal_date}，共 {len(signals)} 条",
        detail=None,
    )


def run_generate_daily_report(
    conn,
    settings: dict[str, Any],
    report_date: str,
) -> WorkflowResult:
    from src.reports.daily_report import build_and_save_daily_report

    try:
        _, saved, message = build_and_save_daily_report(conn, settings, report_date)
    except Exception as exc:
        return WorkflowResult(success=False, message="日报生成失败", detail=str(exc))

    return WorkflowResult(success=saved, message=message)


def run_generate_weekly_report(
    conn,
    settings: dict[str, Any],
    week_start: str,
    week_end: str,
) -> WorkflowResult:
    from src.reports.weekly_report import build_and_save_weekly_report

    try:
        _, saved, message = build_and_save_weekly_report(conn, settings, week_start, week_end)
    except Exception as exc:
        return WorkflowResult(success=False, message="周报生成失败", detail=str(exc))

    return WorkflowResult(success=saved, message=message)


def run_generate_ai_daily_review(
    conn,
    settings: dict[str, Any],
    review_date: str,
) -> WorkflowResult:
    from src.ai_review.review_service import generate_daily_ai_review

    try:
        _, saved, message = generate_daily_ai_review(conn, settings, review_date)
    except Exception as exc:
        return WorkflowResult(success=False, message="AI 日复盘生成失败", detail=str(exc))

    return WorkflowResult(success=saved, message=message)


def run_generate_ai_weekly_review(
    conn,
    settings: dict[str, Any],
    week_start: str,
    week_end: str,
) -> WorkflowResult:
    from src.ai_review.review_service import generate_weekly_ai_review

    try:
        _, saved, message = generate_weekly_ai_review(conn, settings, week_start, week_end)
    except Exception as exc:
        return WorkflowResult(success=False, message="AI 周复盘生成失败", detail=str(exc))

    return WorkflowResult(success=saved, message=message)
