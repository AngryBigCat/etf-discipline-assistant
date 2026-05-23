from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.ai_review.context_builder import (
    DAILY_REPORT_MISSING,
    WEEKLY_REPORT_MISSING,
    build_daily_review_context,
    build_weekly_review_context,
)
from src.config.settings import load_settings
from src.db.repository import (
    save_account_snapshot,
    save_holding_snapshots,
    upsert_daily_prices,
    upsert_daily_report,
    upsert_etf_universe,
    upsert_strategy_signals,
    upsert_weekly_report,
)
from src.db.schema import init_schema


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


@pytest.fixture
def settings():
    return load_settings()


def _seed_base(memory_conn, settings):
    upsert_etf_universe(memory_conn, settings["assets"])
    save_account_snapshot(
        memory_conn,
        {
            "snapshot_date": "2026-05-23",
            "cash_value": 50000,
            "etf_market_value": 50000,
            "total_account_value": 100000,
            "total_position": 0.5,
            "cash_position": 0.5,
        },
    )
    save_holding_snapshots(memory_conn, "2026-05-23", [])
    upsert_daily_prices(
        memory_conn,
        pd.DataFrame(
            [
                {
                    "symbol": "A500",
                    "trade_date": "2026-05-23",
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 1000,
                    "amount": 1000,
                }
            ]
        ),
    )
    upsert_strategy_signals(
        memory_conn,
        [
            {
                "signal_date": "2026-05-23",
                "symbol": "A500",
                "trend_score": 10,
                "drawdown_score": 5,
                "volatility_score": 0,
                "position_score": 0,
                "anti_chase_score": 0,
                "special_score": 0,
                "final_score": 80,
                "action": "strong_buy",
                "suggested_amount": 3000,
                "reason": "测试信号",
                "confidence_level": "normal",
                "review_status": "generated",
            }
        ],
    )


def test_daily_context_with_report(memory_conn, settings):
    _seed_base(memory_conn, settings)
    upsert_daily_report(
        memory_conn,
        {
            "report_date": "2026-05-23",
            "total_position": 0.5,
            "cash_position": 0.5,
            "summary": "测试日报",
            "risk_warning": "测试风险",
            "action_suggestion": "测试建议",
        },
    )
    context = build_daily_review_context(memory_conn, settings, "2026-05-23")
    assert context["missing"] is False
    assert "daily_report" in context
    assert "day_trade_stats" in context
    assert "signals_bucketed" in context


def test_daily_context_without_report(memory_conn, settings):
    _seed_base(memory_conn, settings)
    context = build_daily_review_context(memory_conn, settings, "2026-05-23")
    assert context["missing"] is True
    assert DAILY_REPORT_MISSING in context["message"]


def test_weekly_context_with_report(memory_conn, settings):
    _seed_base(memory_conn, settings)
    upsert_weekly_report(
        memory_conn,
        {
            "week_start": "2026-05-17",
            "week_end": "2026-05-23",
            "summary": "测试周报",
            "discipline_summary": "测试纪律",
            "risk_summary": "测试风险",
            "action_suggestion": "测试建议",
        },
    )
    context = build_weekly_review_context(memory_conn, settings, "2026-05-17", "2026-05-23")
    assert context["missing"] is False
    assert "weekly_report" in context
    assert "trade_summary" in context


def test_weekly_context_without_report(memory_conn, settings):
    _seed_base(memory_conn, settings)
    context = build_weekly_review_context(memory_conn, settings, "2026-05-17", "2026-05-23")
    assert context["missing"] is True
    assert WEEKLY_REPORT_MISSING in context["message"]
