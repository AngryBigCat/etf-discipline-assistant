from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.config.settings import load_settings
from src.db.repository import (
    get_daily_report_by_date,
    list_daily_reports,
    save_account_snapshot,
    save_holding_snapshots,
    upsert_daily_prices,
    upsert_daily_report,
    upsert_etf_universe,
    upsert_indicator_rows,
    upsert_strategy_signals,
)
from src.db.schema import init_schema
from src.reports.daily_report import (
    ACCOUNT_MISSING_MESSAGE,
    build_and_save_daily_report,
    collect_daily_context,
    generate_daily_report_text,
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


def _seed_base(memory_conn, settings, *, snapshot_date="2026-05-23"):
    upsert_etf_universe(memory_conn, settings["assets"])
    save_account_snapshot(
        memory_conn,
        {
            "snapshot_date": snapshot_date,
            "cash_value": 50000,
            "etf_market_value": 50000,
            "total_account_value": 100000,
            "total_position": 0.5,
            "cash_position": 0.5,
        },
    )
    save_holding_snapshots(
        memory_conn,
        snapshot_date,
        [
            {
                "symbol": "A500",
                "quantity": 50000,
                "market_value": 50000,
                "cost": 48000,
                "profit_loss": 2000,
                "profit_loss_rate": 0.04,
                "weight": 0.5,
            }
        ],
    )
    upsert_daily_prices(
        memory_conn,
        pd.DataFrame(
            [
                {
                    "symbol": "A500",
                    "trade_date": snapshot_date,
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
    upsert_indicator_rows(
        memory_conn,
        [
            {
                "symbol": "A500",
                "trade_date": snapshot_date,
                "ma20": 1.0,
                "ma60": 1.0,
                "ma120": 1.0,
                "ma250": 1.0,
                "drawdown_60d": -0.02,
                "drawdown_120d": -0.02,
                "drawdown_250d": -0.02,
                "drawdown_used": -0.02,
                "drawdown_window": 60,
                "volatility_20d": 0.01,
                "return_5d": 0.0,
                "return_10d": 0.0,
                "return_20d": 0.0,
                "confidence_level": "normal",
            }
        ],
    )
    upsert_strategy_signals(
        memory_conn,
        [
            {
                "signal_date": snapshot_date,
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


def test_daily_report_without_trade_logs(memory_conn, settings):
    _seed_base(memory_conn, settings)
    context = collect_daily_context(memory_conn, settings, "2026-05-23")
    report = generate_daily_report_text(context)

    assert "当日交易次数：0 次" in report["summary"]
    assert report["total_position"] == pytest.approx(0.5)
    assert report["cash_position"] == pytest.approx(0.5)


def test_daily_report_with_trade_logs(memory_conn, settings):
    _seed_base(memory_conn, settings)
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-23",
            symbol="A500",
            action="buy",
            amount=1500,
            price=1.0,
            quantity=1500,
            reason="按计划买入",
            user_is_rule_based=True,
        ),
    )
    context = collect_daily_context(memory_conn, settings, "2026-05-23")
    report = generate_daily_report_text(context)

    assert "当日交易次数：1 次" in report["summary"]
    assert "当日买入金额：1,500.00 元" in report["summary"]


def test_daily_report_risk_warning_for_not_rule_based(memory_conn, settings):
    _seed_base(memory_conn, settings)
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-23",
            symbol="A500",
            action="buy",
            amount=5000,
            price=1.0,
            quantity=5000,
            emotion="chasing",
            user_is_rule_based=False,
        ),
    )
    context = collect_daily_context(memory_conn, settings, "2026-05-23")
    report = generate_daily_report_text(context)

    assert "不符合规则" in report["risk_warning"]


def test_daily_report_risk_warning_for_exceed_max(memory_conn, settings):
    _seed_base(memory_conn, settings)
    save_holding_snapshots(
        memory_conn,
        "2026-05-23",
        [
            {
                "symbol": "A500",
                "quantity": 90000,
                "market_value": 90000,
                "cost": 85000,
                "profit_loss": 5000,
                "profit_loss_rate": 0.06,
                "weight": 0.9,
            }
        ],
    )
    save_account_snapshot(
        memory_conn,
        {
            "snapshot_date": "2026-05-23",
            "cash_value": 10000,
            "etf_market_value": 90000,
            "total_account_value": 100000,
            "total_position": 0.9,
            "cash_position": 0.1,
        },
    )
    context = collect_daily_context(memory_conn, settings, "2026-05-23")
    report = generate_daily_report_text(context)

    assert "超过最大仓位" in report["risk_warning"]


def test_upsert_daily_report_overwrites_same_date(memory_conn):
    upsert_daily_report(
        memory_conn,
        {
            "report_date": "2026-05-23",
            "total_position": 0.5,
            "cash_position": 0.5,
            "summary": "旧日报",
            "risk_warning": "旧风险",
            "action_suggestion": "旧建议",
        },
    )
    upsert_daily_report(
        memory_conn,
        {
            "report_date": "2026-05-23",
            "total_position": 0.6,
            "cash_position": 0.4,
            "summary": "新日报",
            "risk_warning": "新风险",
            "action_suggestion": "新建议",
        },
    )
    rows = list_daily_reports(memory_conn)
    assert len(rows) == 1
    assert rows[0]["summary"] == "新日报"


def test_daily_report_without_account_snapshot(memory_conn, settings):
    upsert_etf_universe(memory_conn, settings["assets"])
    report, saved, message = build_and_save_daily_report(memory_conn, settings, "2026-05-23")

    assert saved is False
    assert message == ACCOUNT_MISSING_MESSAGE
    assert report["summary"] == ACCOUNT_MISSING_MESSAGE
    assert get_daily_report_by_date(memory_conn, "2026-05-23") is None
