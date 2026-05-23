from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.config.assets_seed import load_assets_seed
from src.config.settings import load_settings
from src.db.repository import (
    get_strategy_signals_by_date,
    save_account_snapshot,
    save_holding_snapshots,
    upsert_daily_prices,
    upsert_etf_universe,
    upsert_indicator_rows,
    upsert_strategy_signals,
)
from src.db.schema import apply_schema_migrations, init_schema
from src.strategy.signal_generator import generate_signals


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


@pytest.fixture
def settings():
    return load_settings()


def _seed_base(conn, settings, *, total_position=0.5, cash_position=0.5, holdings=None):
    upsert_etf_universe(conn, load_assets_seed())
    save_account_snapshot(
        conn,
        {
            "snapshot_date": "2026-05-23",
            "cash_value": cash_position * 100000,
            "etf_market_value": total_position * 100000,
            "total_account_value": 100000,
            "total_position": total_position,
            "cash_position": cash_position,
        },
    )
    save_holding_snapshots(conn, "2026-05-23", holdings or [])
    upsert_daily_prices(
        conn,
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
        conn,
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


def _seed_kc50(conn, *, weight=0.19, close=1.0):
    upsert_daily_prices(
        conn,
        pd.DataFrame(
            [
                {
                    "symbol": "KC50",
                    "trade_date": "2026-05-23",
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1000,
                    "amount": 1000,
                }
            ]
        ),
    )
    upsert_indicator_rows(
        conn,
        [
            {
                "symbol": "KC50",
                "trade_date": "2026-05-23",
                "ma20": 1.1,
                "ma60": 1.1,
                "ma120": 1.2,
                "ma250": 1.3,
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
    save_holding_snapshots(
        conn,
        "2026-05-23",
        [
            {
                "snapshot_date": "2026-05-23",
                "symbol": "KC50",
                "quantity": 10000,
                "market_value": weight * 100000,
                "cost": weight * 90000,
                "profit_loss": weight * 10000,
                "profit_loss_rate": 0.1,
                "weight": weight,
            }
        ],
    )


def test_exceed_max_forces_stop_buy(memory_conn, settings):
    _seed_base(
        memory_conn,
        settings,
        holdings=[
            {
                "snapshot_date": "2026-05-23",
                "symbol": "A500",
                "quantity": 100000,
                "market_value": 70000,
                "cost": 60000,
                "profit_loss": 10000,
                "profit_loss_rate": 0.1,
                "weight": 0.7,
            }
        ],
    )
    signals, _ = generate_signals(memory_conn, settings, signal_date="2026-05-23")
    a500 = next(item for item in signals if item.symbol == "A500")
    assert a500.action == "stop_buy"
    assert a500.suggested_amount == 0


def test_total_position_over_80_forces_stop_buy(memory_conn, settings):
    _seed_base(
        memory_conn,
        settings,
        total_position=0.85,
        cash_position=0.15,
        holdings=[
            {
                "snapshot_date": "2026-05-23",
                "symbol": "A500",
                "quantity": 10000,
                "market_value": 85000,
                "cost": 80000,
                "profit_loss": 5000,
                "profit_loss_rate": 0.05,
                "weight": 0.85,
            }
        ],
    )
    signals, _ = generate_signals(memory_conn, settings, signal_date="2026-05-23")
    assert signals
    assert all(signal.action == "stop_buy" for signal in signals)
    assert all(signal.suggested_amount == 0 for signal in signals)


def test_watch_only_assets_not_generated(memory_conn, settings):
    _seed_base(memory_conn, settings)
    signals, context = generate_signals(memory_conn, settings, signal_date="2026-05-23")
    symbols = {signal.symbol for signal in signals}
    assert "SP500" not in symbols
    assert "NASDAQ100" not in symbols
    watch_symbols = {asset["symbol"] for asset in context["watch_only_assets"]}
    assert "SP500" in watch_symbols
    assert "NASDAQ100" in watch_symbols


def test_generate_signals_persistable(memory_conn, settings):
    _seed_base(memory_conn, settings)
    signals, _ = generate_signals(memory_conn, settings, signal_date="2026-05-23")
    upsert_strategy_signals(memory_conn, [signal.to_db_row() for signal in signals])
    count = memory_conn.execute("SELECT COUNT(*) AS c FROM strategy_signal").fetchone()["c"]
    assert count == len(signals)


def test_kc50_special_score_not_zero(memory_conn, settings):
    _seed_base(memory_conn, settings)
    _seed_kc50(memory_conn, weight=0.19, close=1.0)
    signals, _ = generate_signals(memory_conn, settings, signal_date="2026-05-23")
    kc50 = next(signal for signal in signals if signal.symbol == "KC50")
    assert kc50.special_score != 0


def test_special_score_persisted_after_upsert(memory_conn, settings):
    _seed_base(memory_conn, settings)
    _seed_kc50(memory_conn, weight=0.19, close=1.0)
    signals, _ = generate_signals(memory_conn, settings, signal_date="2026-05-23")
    kc50 = next(signal for signal in signals if signal.symbol == "KC50")
    upsert_strategy_signals(memory_conn, [signal.to_db_row() for signal in signals])
    row = get_strategy_signals_by_date(memory_conn, "2026-05-23")
    kc50_row = next(item for item in row if item["symbol"] == "KC50")
    assert kc50_row["special_score"] == pytest.approx(kc50.special_score)
    assert kc50_row["special_score"] != 0


def test_migration_adds_special_score_column():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE strategy_signal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            trend_score REAL DEFAULT 0,
            drawdown_score REAL DEFAULT 0,
            volatility_score REAL DEFAULT 0,
            position_score REAL DEFAULT 0,
            anti_chase_score REAL DEFAULT 0,
            final_score REAL DEFAULT 0,
            action TEXT,
            suggested_amount REAL DEFAULT 0,
            reason TEXT,
            confidence_level TEXT DEFAULT 'normal',
            review_status TEXT DEFAULT 'generated',
            reviewed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(signal_date, symbol)
        )
        """
    )
    apply_schema_migrations(conn)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(strategy_signal)").fetchall()]
    assert "special_score" in columns

    conn.execute(
        "INSERT INTO strategy_signal (signal_date, symbol) VALUES ('2026-05-23', 'KC50')"
    )
    stored = conn.execute(
        "SELECT special_score FROM strategy_signal WHERE symbol = 'KC50'"
    ).fetchone()
    assert stored["special_score"] == 0
