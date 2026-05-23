from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest

from src.backtest.data_loader import load_multi_symbol_prices
from src.backtest.portfolio import (
    PortfolioAssetConfig,
    PortfolioBacktestConfig,
    run_portfolio_backtest,
    validate_portfolio_weights,
)
from src.backtest.service import run_and_save_portfolio_backtest
from src.db.repository import get_backtest_positions, upsert_daily_prices
from src.db.schema import init_schema


def _trade_dates(count: int, start: date = date(2024, 1, 2)) -> list[str]:
    dates: list[str] = []
    current = start
    added = 0
    while added < count:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
            added += 1
        current += timedelta(days=1)
    return dates


def _make_symbol_prices(
    symbol: str,
    dates: list[str],
    *,
    close: float | list[float],
) -> pd.DataFrame:
    if isinstance(close, (int, float)):
        closes = [float(close)] * len(dates)
    else:
        closes = list(close)
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(dates),
            "trade_date": dates,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1000.0] * len(dates),
            "amount": [value * 1000 for value in closes],
        }
    )


def _seed_two_symbol_prices(
    conn: sqlite3.Connection,
    *,
    count: int = 60,
    a500_close: float | list[float] = 10.0,
    dividend_close: float | list[float] = 5.0,
    dividend_start_offset: int = 0,
) -> tuple[list[str], list[str]]:
    all_dates = _trade_dates(count + dividend_start_offset)
    a500_dates = all_dates[dividend_start_offset:]
    dividend_dates = all_dates
    upsert_daily_prices(conn, _make_symbol_prices("A500", a500_dates, close=a500_close))
    upsert_daily_prices(conn, _make_symbol_prices("DIVIDEND", dividend_dates, close=dividend_close))
    conn.commit()
    return a500_dates, dividend_dates


@pytest.fixture
def memory_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def test_load_multi_symbol_prices_reads_multiple_symbols(memory_conn: sqlite3.Connection):
    _seed_two_symbol_prices(memory_conn)
    result = load_multi_symbol_prices(
        memory_conn,
        ["A500", "DIVIDEND"],
        "2024-01-01",
        "2024-12-31",
    )
    assert result.valid is True
    assert set(result.price_dfs.keys()) == {"A500", "DIVIDEND"}
    assert len(result.trade_dates) >= 30


def test_load_multi_symbol_prices_uses_intersection_range(memory_conn: sqlite3.Connection):
    a500_dates, _ = _seed_two_symbol_prices(memory_conn, count=60, dividend_start_offset=10)
    result = load_multi_symbol_prices(
        memory_conn,
        ["A500", "DIVIDEND"],
        "2024-01-01",
        "2024-12-31",
    )
    assert result.valid is True
    assert result.actual_start_date == a500_dates[0]
    assert result.actual_end_date == a500_dates[-1]


def test_load_multi_symbol_prices_requires_two_valid_symbols(memory_conn: sqlite3.Connection):
    dates = _trade_dates(40)
    upsert_daily_prices(memory_conn, _make_symbol_prices("A500", dates, close=10.0))
    memory_conn.commit()

    result = load_multi_symbol_prices(memory_conn, ["A500", "DIVIDEND"], "2024-01-01", "2024-12-31")
    assert result.valid is False
    assert "DIVIDEND" in result.errors
    assert result.error_message


def test_validate_portfolio_weights_rejects_over_100_percent():
    assets = [
        PortfolioAssetConfig("A500", 0.6),
        PortfolioAssetConfig("DIVIDEND", 0.5),
    ]
    message = validate_portfolio_weights(assets)
    assert message is not None
    assert "超过 100%" in message


def test_portfolio_dca_allocates_by_normalized_weights(memory_conn: sqlite3.Connection):
    _seed_two_symbol_prices(memory_conn, count=60)
    load_result = load_multi_symbol_prices(memory_conn, ["A500", "DIVIDEND"], "2024-01-01", "2024-12-31")
    config = PortfolioBacktestConfig(
        assets=[
            PortfolioAssetConfig("A500", 0.5),
            PortfolioAssetConfig("DIVIDEND", 0.2),
        ],
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_cash=10000.0,
        fixed_amount=700.0,
        frequency="monthly",
        strategy_name="portfolio_dca",
    )
    result = run_portfolio_backtest(config, load_result.price_dfs, load_result.trade_dates)
    assert result.valid is True
    first_invest_date = load_result.trade_dates[0]
    first_trades = [trade for trade in result.trades if trade.trade_date == first_invest_date]
    assert len(first_trades) == 2
    amounts = {trade.symbol: trade.amount for trade in first_trades}
    assert amounts["A500"] == pytest.approx(500.0)
    assert amounts["DIVIDEND"] == pytest.approx(200.0)


def test_portfolio_backtest_cash_never_negative(memory_conn: sqlite3.Connection):
    _seed_two_symbol_prices(memory_conn, count=60)
    load_result = load_multi_symbol_prices(memory_conn, ["A500", "DIVIDEND"], "2024-01-01", "2024-12-31")
    config = PortfolioBacktestConfig(
        assets=[
            PortfolioAssetConfig("A500", 0.5),
            PortfolioAssetConfig("DIVIDEND", 0.5),
        ],
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_cash=5000.0,
        fixed_amount=3000.0,
        frequency="monthly",
        strategy_name="portfolio_dca",
    )
    result = run_portfolio_backtest(config, load_result.price_dfs, load_result.trade_dates)
    assert result.valid is True
    assert all(point.cash_value >= -1e-9 for point in result.equity_curve)


def test_portfolio_equity_curve_matches_cash_plus_positions(memory_conn: sqlite3.Connection):
    _seed_two_symbol_prices(memory_conn, count=60)
    load_result = load_multi_symbol_prices(memory_conn, ["A500", "DIVIDEND"], "2024-01-01", "2024-12-31")
    config = PortfolioBacktestConfig(
        assets=[
            PortfolioAssetConfig("A500", 0.5),
            PortfolioAssetConfig("DIVIDEND", 0.5),
        ],
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_cash=10000.0,
        fixed_amount=1000.0,
        frequency="monthly",
        strategy_name="portfolio_dca",
    )
    result = run_portfolio_backtest(config, load_result.price_dfs, load_result.trade_dates)
    assert result.valid is True
    for point in result.equity_curve:
        assert point.total_value == pytest.approx(point.cash_value + point.position_value)


def test_portfolio_dca_has_no_sell_trades(memory_conn: sqlite3.Connection):
    _seed_two_symbol_prices(memory_conn, count=60)
    load_result = load_multi_symbol_prices(memory_conn, ["A500", "DIVIDEND"], "2024-01-01", "2024-12-31")
    config = PortfolioBacktestConfig(
        assets=[
            PortfolioAssetConfig("A500", 0.5),
            PortfolioAssetConfig("DIVIDEND", 0.5),
        ],
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_cash=10000.0,
        fixed_amount=1000.0,
        frequency="monthly",
        strategy_name="portfolio_dca",
    )
    result = run_portfolio_backtest(config, load_result.price_dfs, load_result.trade_dates)
    assert all(trade.action == "buy" for trade in result.trades)


def test_portfolio_rebalance_generates_rebalance_trades(memory_conn: sqlite3.Connection):
    dates = _trade_dates(120)
    a500_closes = [10.0 + index * 0.5 for index in range(len(dates))]
    upsert_daily_prices(memory_conn, _make_symbol_prices("A500", dates, close=a500_closes))
    upsert_daily_prices(memory_conn, _make_symbol_prices("DIVIDEND", dates, close=5.0))
    memory_conn.commit()
    load_result = load_multi_symbol_prices(memory_conn, ["A500", "DIVIDEND"], "2024-01-01", "2024-12-31")
    config = PortfolioBacktestConfig(
        assets=[
            PortfolioAssetConfig("A500", 0.5),
            PortfolioAssetConfig("DIVIDEND", 0.5),
        ],
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_cash=100000.0,
        fixed_amount=1000.0,
        frequency="monthly",
        strategy_name="portfolio_rebalance",
        rebalance_threshold=0.05,
    )
    result = run_portfolio_backtest(config, load_result.price_dfs, load_result.trade_dates)
    rebalance_trades = [trade for trade in result.trades if "再平衡" in trade.reason]
    assert rebalance_trades
    assert any(trade.action == "sell" for trade in rebalance_trades)


def test_portfolio_backtest_does_not_touch_real_tables(memory_conn: sqlite3.Connection):
    _seed_two_symbol_prices(memory_conn, count=60)
    trade_log_count = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    holding_count = memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0]
    account_count = memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0]

    config = PortfolioBacktestConfig(
        assets=[
            PortfolioAssetConfig("A500", 0.5),
            PortfolioAssetConfig("DIVIDEND", 0.5),
        ],
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_cash=10000.0,
        fixed_amount=1000.0,
        frequency="monthly",
        strategy_name="portfolio_dca",
    )
    run_id, _, message = run_and_save_portfolio_backtest(memory_conn, config)
    assert run_id is not None
    assert "完成" in message

    assert memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0] == trade_log_count
    assert memory_conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0] == holding_count
    assert memory_conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0] == account_count


def test_backtest_positions_saved(memory_conn: sqlite3.Connection):
    _seed_two_symbol_prices(memory_conn, count=60)
    config = PortfolioBacktestConfig(
        assets=[
            PortfolioAssetConfig("A500", 0.5),
            PortfolioAssetConfig("DIVIDEND", 0.5),
        ],
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_cash=10000.0,
        fixed_amount=1000.0,
        frequency="monthly",
        strategy_name="portfolio_dca",
    )
    run_id, result, _ = run_and_save_portfolio_backtest(memory_conn, config)
    assert run_id is not None
    positions = get_backtest_positions(memory_conn, int(run_id))
    assert len(positions) == len(result.positions)
    assert {row["symbol"] for row in positions} == {"A500", "DIVIDEND"}


def test_run_and_save_portfolio_backtest_rejects_overweight(memory_conn: sqlite3.Connection):
    _seed_two_symbol_prices(memory_conn, count=60)
    config = PortfolioBacktestConfig(
        assets=[
            PortfolioAssetConfig("A500", 0.7),
            PortfolioAssetConfig("DIVIDEND", 0.5),
        ],
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_cash=10000.0,
        fixed_amount=1000.0,
        frequency="monthly",
        strategy_name="portfolio_dca",
    )
    run_id, result, message = run_and_save_portfolio_backtest(memory_conn, config)
    assert run_id is None
    assert result.valid is False
    assert "超过 100%" in message
