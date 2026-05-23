from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.config.settings import load_settings
from src.db.repository import (
    save_account_snapshot,
    save_holding_snapshots,
    upsert_daily_prices,
    upsert_etf_universe,
    upsert_indicator_rows,
    upsert_strategy_signals,
)
from src.db.schema import init_schema
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
    upsert_etf_universe(conn, settings["assets"])
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
