from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest

from src.backtest.models import BacktestConfig
from src.backtest.service import load_backtest_detail, run_and_save_backtest
from src.db.repository import upsert_daily_prices
from src.db.schema import init_schema


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def _seed_prices(conn, count: int = 60) -> BacktestConfig:
    dates: list[str] = []
    current = date(2025, 1, 1)
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    price_df = pd.DataFrame(
        {
            "symbol": ["A500"] * count,
            "trade_date": dates,
            "open": [10.0] * count,
            "high": [10.0] * count,
            "low": [10.0] * count,
            "close": [10.0] * count,
            "volume": [1000.0] * count,
            "amount": [10000.0] * count,
        }
    )
    upsert_daily_prices(conn, price_df)
    return BacktestConfig(
        symbol="A500",
        strategy_name="baseline_dca",
        start_date=dates[0],
        end_date=dates[-1],
        initial_cash=10000,
        fixed_amount=1000,
        frequency="monthly",
    )


def test_run_and_save_backtest_persists_all_tables(memory_conn):
    config = _seed_prices(memory_conn)
    run_id, result, message = run_and_save_backtest(memory_conn, config)
    assert run_id is not None
    assert result.valid is True
    assert message == "回测已完成"

    detail = load_backtest_detail(memory_conn, run_id)
    assert detail["run"]["symbol"] == "A500"
    assert detail["result"]["trade_count"] == result.trade_count
    assert len(detail["trades"]) == result.trade_count
    assert len(detail["equity_curve"]) == len(result.equity_curve)


def test_run_and_save_backtest_empty_data(memory_conn):
    config = BacktestConfig(
        symbol="A500",
        strategy_name="baseline_dca",
        start_date="2025-01-01",
        end_date="2025-03-01",
        initial_cash=10000,
        fixed_amount=1000,
        frequency="monthly",
    )
    run_id, result, message = run_and_save_backtest(memory_conn, config)
    assert run_id is None
    assert result.valid is False
    assert message

    run_count = memory_conn.execute("SELECT COUNT(*) FROM backtest_run").fetchone()[0]
    assert run_count == 0
