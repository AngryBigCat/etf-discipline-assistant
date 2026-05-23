from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest

from src.backtest.engine import run_backtest
from src.backtest.metrics import calculate_annualized_return
from src.backtest.models import BacktestConfig
from src.db.repository import upsert_daily_prices
from src.db.schema import init_schema


def _trade_dates(count: int, start: date = date(2025, 1, 1)) -> list[str]:
    dates: list[str] = []
    current = start
    added = 0
    while added < count:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
            added += 1
        current += timedelta(days=1)
    return dates


def _make_price_df(count: int = 60, close: float = 10.0) -> pd.DataFrame:
    dates = _trade_dates(count)
    return pd.DataFrame(
        {
            "symbol": ["A500"] * count,
            "trade_date": dates,
            "open": [close] * count,
            "high": [close] * count,
            "low": [close] * count,
            "close": [close] * count,
            "volume": [1000.0] * count,
            "amount": [close * 1000] * count,
        }
    )


def _base_config(**overrides) -> BacktestConfig:
    price_df = _make_price_df()
    config = BacktestConfig(
        symbol="A500",
        strategy_name="baseline_dca",
        start_date=str(price_df.iloc[0]["trade_date"]),
        end_date=str(price_df.iloc[-1]["trade_date"]),
        initial_cash=10000,
        fixed_amount=1000,
        frequency="monthly",
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def test_baseline_dca_buys_on_invest_days():
    config = _base_config()
    result = run_backtest(config, _make_price_df())
    assert result.valid is True
    assert result.trade_count >= 1


def test_cash_never_negative():
    config = _base_config(initial_cash=2500, fixed_amount=1000)
    result = run_backtest(config, _make_price_df())
    assert all(point.cash_value >= 0 for point in result.equity_curve)
    assert all(trade.amount <= 1000 for trade in result.trades)


def test_buy_quantity_equals_amount_over_close():
    config = _base_config()
    result = run_backtest(config, _make_price_df(close=10.0))
    for trade in result.trades:
        assert trade.quantity == pytest.approx(trade.amount / trade.price)


def test_equity_curve_has_daily_records():
    price_df = _make_price_df(60)
    config = _base_config()
    result = run_backtest(config, price_df)
    assert len(result.equity_curve) == len(price_df)


def test_skip_non_positive_price():
    price_df = _make_price_df(60).copy()[["symbol", "trade_date", "close"]]
    bad_date = str(price_df.iloc[10]["trade_date"])
    price_df.loc[10, "close"] = 0
    config = _base_config()
    result = run_backtest(config, price_df)
    assert all(trade.trade_date != bad_date for trade in result.trades)
    assert bad_date not in {point.trade_date for point in result.equity_curve}


def test_zero_close_does_not_collapse_total_value():
    price_df = _make_price_df(60, close=10.0)[["symbol", "trade_date", "close"]]
    price_df.loc[10, "close"] = 0
    config = _base_config(initial_cash=10000, fixed_amount=1000)
    result = run_backtest(config, price_df)
    assert result.valid is True
    assert result.final_quantity > 0
    assert len(result.equity_curve) == 59
    for point in result.equity_curve:
        assert point.total_value == pytest.approx(point.cash_value + point.position_value)
        if point.position_value > 0:
            assert point.total_value > point.cash_value


def test_equity_curve_total_value_not_cash_only_while_holding():
    price_df = _make_price_df(60, close=10.0)[["symbol", "trade_date", "close"]]
    price_df.loc[20, "close"] = 0
    price_df.loc[21, "close"] = 0
    config = _base_config(initial_cash=10000, fixed_amount=1000)
    result = run_backtest(config, price_df)
    assert result.valid is True
    holding_points = [point for point in result.equity_curve if point.position_value > 0]
    assert holding_points
    for point in holding_points:
        assert point.position_value > 0
        assert point.total_value > point.cash_value


def test_backtest_filters_holiday_price_spikes_from_equity_curve():
    dates = _trade_dates(120, start=date(2025, 6, 1))
    price_df = pd.DataFrame(
        {
            "symbol": ["A500"] * len(dates),
            "trade_date": dates,
            "close": [1.2] * len(dates),
        }
    )
    for bad_date, bad_close, rebound_date, rebound_close in [
        ("2025-10-01", 0.8681, "2025-10-09", 1.196),
        ("2026-01-01", 0.8334, "2026-01-05", 1.211),
    ]:
        if bad_date in price_df["trade_date"].values:
            price_df.loc[price_df["trade_date"] == bad_date, "close"] = bad_close
        if rebound_date in price_df["trade_date"].values:
            price_df.loc[price_df["trade_date"] == rebound_date, "close"] = rebound_close

    config = BacktestConfig(
        symbol="A500",
        strategy_name="drawdown_boost",
        start_date=str(price_df.iloc[0]["trade_date"]),
        end_date=str(price_df.iloc[-1]["trade_date"]),
        initial_cash=100000,
        fixed_amount=3000,
        frequency="monthly",
    )
    result = run_backtest(config, price_df)
    assert result.valid is True
    prev = result.equity_curve[0]
    for point in result.equity_curve[1:]:
        if prev.position_value > 1000 and point.position_value > 0:
            assert point.total_value / prev.total_value > 0.88
        prev = point

def test_empty_data_returns_friendly_error():
    config = _base_config()
    result = run_backtest(config, pd.DataFrame(columns=["symbol", "trade_date", "close"]))
    assert result.valid is False
    assert "为空" in result.error_message


def test_backtest_does_not_touch_real_tables():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)

    price_df = _make_price_df(60)
    upsert_daily_prices(conn, price_df)
    conn.commit()

    trade_log_count = conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    holding_count = conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0]
    account_count = conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0]

    config = _base_config(
        start_date=str(price_df.iloc[0]["trade_date"]),
        end_date=str(price_df.iloc[-1]["trade_date"]),
    )
    result = run_backtest(config, price_df)
    assert result.valid is True

    assert conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0] == trade_log_count
    assert conn.execute("SELECT COUNT(*) FROM holding_snapshot").fetchone()[0] == holding_count
    assert conn.execute("SELECT COUNT(*) FROM account_snapshot").fetchone()[0] == account_count


def test_backtest_uses_actual_date_range_for_metrics():
    price_df = _make_price_df(60, close=10.0)
    price_df = price_df[["symbol", "trade_date", "close"]]
    actual_start = str(price_df.iloc[0]["trade_date"])
    actual_end = str(price_df.iloc[-1]["trade_date"])
    config = BacktestConfig(
        symbol="A500",
        strategy_name="baseline_dca",
        start_date="2021-01-01",
        end_date=actual_end,
        initial_cash=10000,
        fixed_amount=1000,
        frequency="monthly",
    )
    result = run_backtest(config, price_df)
    assert result.valid is True
    assert result.requested_start_date == "2021-01-01"
    assert result.actual_start_date == actual_start
    assert result.actual_start_date > result.requested_start_date
    assert result.trading_days == len(price_df)
    expected_annualized = calculate_annualized_return(
        result.final_value,
        config.initial_cash,
        result.actual_start_date,
        result.actual_end_date,
    )
    assert result.annualized_return == expected_annualized
