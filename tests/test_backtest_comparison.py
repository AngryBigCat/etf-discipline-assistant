from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest

from src.backtest.metrics import calculate_cash_utilization
from src.backtest.models import BacktestConfig
from src.backtest.service import run_and_save_backtest, run_backtest_comparison
from src.db.repository import list_backtest_run_summaries, upsert_daily_prices
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


def test_cash_utilization_calculation():
    assert calculate_cash_utilization(3000, 10000) == pytest.approx(0.3)
    assert calculate_cash_utilization(3000, 0) == 0.0


def test_run_backtest_comparison_runs_multiple_strategies(memory_conn):
    base_config = _seed_prices(memory_conn)
    items = run_backtest_comparison(
        memory_conn,
        base_config,
        ["baseline_dca", "ma_filter_dca", "drawdown_boost"],
    )
    assert len(items) == 3
    assert all(item["run_id"] is not None for item in items)
    run_count = memory_conn.execute("SELECT COUNT(*) FROM backtest_run").fetchone()[0]
    assert run_count == 3


def test_run_backtest_comparison_single_failure_does_not_block_others(memory_conn):
    base_config = _seed_prices(memory_conn)
    items = run_backtest_comparison(
        memory_conn,
        base_config,
        ["baseline_dca", "unknown_strategy", "drawdown_boost"],
    )
    assert len(items) == 3
    assert items[0]["run_id"] is not None
    assert items[1]["run_id"] is None
    assert items[2]["run_id"] is not None


def test_list_backtest_run_summaries_returns_metrics(memory_conn):
    config = _seed_prices(memory_conn)
    run_id, result, _ = run_and_save_backtest(memory_conn, config)
    assert run_id is not None
    rows = list_backtest_run_summaries(memory_conn, limit=5)
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == run_id
    assert row["final_value"] == result.final_value
    assert row["cash_utilization"] == result.cash_utilization


def test_backtest_comparison_does_not_touch_real_tables(memory_conn):
    base_config = _seed_prices(memory_conn)
    trade_log_count = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    holding_count = memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0]
    account_count = memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0]

    run_backtest_comparison(memory_conn, base_config, ["baseline_dca", "ma_filter_dca"])

    assert memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0] == trade_log_count
    assert memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0] == holding_count
    assert memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0] == account_count
