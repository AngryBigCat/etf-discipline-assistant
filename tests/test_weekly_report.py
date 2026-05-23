from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.config.assets_seed import load_assets_seed
from src.config.settings import load_settings
from src.db.repository import (
    get_weekly_report,
    list_weekly_reports,
    save_account_snapshot,
    save_holding_snapshots,
    upsert_etf_universe,
    upsert_strategy_signals,
    upsert_weekly_report,
)
from src.db.schema import init_schema
from src.reports.weekly_report import (
    ACCOUNT_MISSING_MESSAGE,
    build_and_save_weekly_report,
    collect_weekly_context,
    generate_weekly_report_text,
)
from src.trading.trade_log import TradeLogInput, create_manual_trade


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
    upsert_etf_universe(memory_conn, load_assets_seed())
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


def test_weekly_report_trade_counts(memory_conn, settings):
    _seed_base(memory_conn, settings)
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-20",
            symbol="A500",
            action="buy",
            amount=1000,
            price=1.0,
            quantity=1000,
            user_is_rule_based=True,
        ),
    )
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-21",
            symbol="A500",
            action="sell",
            amount=500,
            price=1.0,
            quantity=500,
            user_is_rule_based=True,
        ),
    )
    context = collect_weekly_context(memory_conn, settings, "2026-05-17", "2026-05-23")
    report = generate_weekly_report_text(context)

    assert "本周交易次数：2 次" in report["summary"]
    assert "买入次数：1 次" in report["summary"]
    assert "卖出次数：1 次" in report["summary"]


def test_weekly_report_compliance_rate(memory_conn, settings):
    _seed_base(memory_conn, settings)
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-22",
            symbol="A500",
            action="buy",
            amount=1000,
            user_is_rule_based=True,
        ),
    )
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-23",
            symbol="KC50",
            action="buy",
            amount=2000,
            emotion="chasing",
            user_is_rule_based=False,
        ),
    )
    context = collect_weekly_context(memory_conn, settings, "2026-05-17", "2026-05-23")
    report = generate_weekly_report_text(context)

    assert "纪律执行率：50.00%" in report["discipline_summary"]


def test_weekly_report_emotion_counts(memory_conn, settings):
    _seed_base(memory_conn, settings)
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-20",
            symbol="A500",
            action="buy",
            amount=1000,
            emotion="chasing",
            user_is_rule_based=False,
        ),
    )
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-21",
            symbol="KC50",
            action="buy",
            amount=1000,
            emotion="panic",
            user_is_rule_based=False,
        ),
    )
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-22",
            symbol="HS300",
            action="buy",
            amount=1000,
            emotion="temporary",
            user_is_rule_based=False,
        ),
    )
    context = collect_weekly_context(memory_conn, settings, "2026-05-17", "2026-05-23")
    report = generate_weekly_report_text(context)

    assert "追涨次数：1 次" in report["discipline_summary"]
    assert "恐慌次数：1 次" in report["discipline_summary"]
    assert "临时决策次数：1 次" in report["discipline_summary"]


def test_upsert_weekly_report_overwrites_same_week(memory_conn):
    upsert_weekly_report(
        memory_conn,
        {
            "week_start": "2026-05-17",
            "week_end": "2026-05-23",
            "summary": "旧周报",
            "discipline_summary": "旧纪律",
            "risk_summary": "旧风险",
            "action_suggestion": "旧建议",
        },
    )
    upsert_weekly_report(
        memory_conn,
        {
            "week_start": "2026-05-17",
            "week_end": "2026-05-23",
            "summary": "新周报",
            "discipline_summary": "新纪律",
            "risk_summary": "新风险",
            "action_suggestion": "新建议",
        },
    )
    rows = list_weekly_reports(memory_conn)
    assert len(rows) == 1
    assert rows[0]["summary"] == "新周报"
    saved = get_weekly_report(memory_conn, "2026-05-17", "2026-05-23")
    assert saved is not None
    assert saved["discipline_summary"] == "新纪律"


def test_weekly_report_without_account_snapshot(memory_conn, settings):
    upsert_etf_universe(memory_conn, load_assets_seed())
    report, saved, message = build_and_save_weekly_report(
        memory_conn,
        settings,
        "2026-05-17",
        "2026-05-23",
    )

    assert saved is False
    assert message == ACCOUNT_MISSING_MESSAGE
    assert report["summary"] == ACCOUNT_MISSING_MESSAGE
    assert get_weekly_report(memory_conn, "2026-05-17", "2026-05-23") is None
