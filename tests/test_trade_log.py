from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.config.assets_seed import load_assets_seed
from src.config.settings import load_settings
from src.db.repository import (
    get_strategy_signals_by_date,
    get_trade_log_by_id,
    get_trade_logs,
    save_account_snapshot,
    save_holding_snapshots,
    upsert_daily_prices,
    upsert_etf_universe,
    upsert_indicator_rows,
    upsert_strategy_signals,
)
from src.db.schema import apply_schema_migrations, init_schema
from src.trading.trade_log import (
    TradeLogInput,
    create_buy_from_signal,
    create_ignore_from_signal,
    create_manual_trade,
    get_trade_summary,
)


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


@pytest.fixture
def settings():
    return load_settings()


def _seed_signal(memory_conn, settings):
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
    upsert_indicator_rows(
        memory_conn,
        [
            {
                "symbol": "A500",
                "trade_date": "2026-05-23",
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
    rows = get_strategy_signals_by_date(memory_conn, "2026-05-23")
    return dict(rows[0])


def test_create_buy_from_signal(memory_conn, settings):
    signal = _seed_signal(memory_conn, settings)
    trade_id = create_buy_from_signal(
        memory_conn,
        signal,
        trade_date="2026-05-23",
        amount=3000,
        price=1.0,
        quantity=3000,
        reason="按计划买入",
    )
    trade = get_trade_log_by_id(memory_conn, trade_id)
    assert trade is not None
    assert trade["symbol"] == "A500"
    assert trade["signal_id"] == signal["id"]
    assert trade["action"] == "buy"
    assert trade["is_rule_based"] == 1
    assert trade["execution_status"] == "matched_signal"

    updated = get_strategy_signals_by_date(memory_conn, "2026-05-23")[0]
    assert updated["review_status"] == "executed"


def test_manual_trade_saved_and_queryable(memory_conn, settings):
    upsert_etf_universe(memory_conn, load_assets_seed())
    trade_id = create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-23",
            symbol="A500",
            action="buy",
            amount=1000,
            price=1.0,
            quantity=1000,
            reason="手动买入",
            emotion="temporary",
            user_is_rule_based=False,
        ),
    )
    trade = get_trade_log_by_id(memory_conn, trade_id)
    assert trade["execution_status"] == "manual"
    rows = get_trade_logs(memory_conn, start_date="2026-05-23", end_date="2026-05-23")
    assert len(rows) == 1


def test_ignore_signal_writes_trade_log(memory_conn, settings):
    signal = _seed_signal(memory_conn, settings)
    trade_id = create_ignore_from_signal(memory_conn, signal)
    trade = get_trade_log_by_id(memory_conn, trade_id)
    assert trade["action"] == "ignore"
    assert trade["execution_status"] == "ignored"
    assert trade["is_rule_based"] == 1


def test_trade_summary_counts(memory_conn, settings):
    signal = _seed_signal(memory_conn, settings)
    create_buy_from_signal(
        memory_conn,
        signal,
        trade_date="2026-05-23",
        amount=3000,
        price=1.0,
        quantity=3000,
    )
    create_manual_trade(
        memory_conn,
        TradeLogInput(
            trade_date="2026-05-23",
            symbol="KC50",
            action="buy",
            amount=5000,
            price=1.0,
            quantity=5000,
            emotion="chasing",
            user_is_rule_based=False,
        ),
    )
    summary = get_trade_summary(memory_conn, "2026-05-23", "2026-05-23")
    assert summary["total_count"] == 2
    assert summary["buy_count"] == 2
    assert summary["rule_based_count"] == 1
    assert summary["not_rule_based_count"] == 1
    assert summary["chasing_count"] == 1
    assert summary["compliance_rate"] == pytest.approx(0.5)


def test_migration_adds_trade_log_columns():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            signal_id INTEGER,
            action TEXT NOT NULL,
            amount REAL NOT NULL,
            price REAL,
            quantity REAL,
            reason TEXT,
            emotion TEXT,
            is_rule_based INTEGER DEFAULT 1,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    apply_schema_migrations(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(trade_log)").fetchall()}
    assert "suggested_amount" in columns
    assert "deviation_amount" in columns
    assert "execution_status" in columns

    conn.execute(
        """
        INSERT INTO trade_log (trade_date, symbol, action, amount)
        VALUES ('2026-05-23', 'A500', 'buy', 1000)
        """
    )
    row = conn.execute("SELECT execution_status FROM trade_log").fetchone()
    assert row["execution_status"] == "recorded"
