from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from src.backtest.models import BacktestConfig
from src.backtest.strategies import (
    StrategyContext,
    baseline_dca,
    build_invest_dates,
    drawdown_boost,
    ma_filter_dca,
    should_invest_on_date,
)


def _trade_dates(count: int, start: date = date(2026, 1, 1)) -> list[str]:
    dates: list[str] = []
    current = start
    added = 0
    while added < count:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
            added += 1
        current += timedelta(days=1)
    return dates


def test_monthly_invest_only_first_trading_day():
    dates = _trade_dates(40, start=date(2026, 1, 1))
    invest_dates = build_invest_dates(dates, "monthly")
    jan_dates = [d for d in dates if d.startswith("2026-01")]
    assert should_invest_on_date(jan_dates[0], "monthly", invest_dates) is True
    assert should_invest_on_date(jan_dates[1], "monthly", invest_dates) is False


def test_weekly_invest_only_first_trading_day():
    dates = _trade_dates(20, start=date(2026, 1, 5))
    invest_dates = build_invest_dates(dates, "weekly")
    week_dates = dates[:5]
    assert should_invest_on_date(week_dates[0], "weekly", invest_dates) is True
    assert should_invest_on_date(week_dates[1], "weekly", invest_dates) is False


def test_ma_filter_dca_boosts_below_ma250():
    dates = _trade_dates(260)
    close_values = [100.0] * 259 + [80.0]
    price_df = pd.DataFrame({"trade_date": dates, "close": close_values})
    ma250 = pd.Series([100.0] * 260)
    price_drawdown = pd.Series([0.0] * 260)
    config = BacktestConfig(
        symbol="A500",
        strategy_name="ma_filter_dca",
        start_date=dates[0],
        end_date=dates[-1],
        initial_cash=100000,
        fixed_amount=1000,
        frequency="monthly",
    )
    invest_dates = {dates[259]}
    ctx = StrategyContext(
        index=259,
        price_df=price_df,
        ma250=ma250,
        price_drawdown=price_drawdown,
        cash=5000,
        config=config,
        invest_dates=invest_dates,
    )
    amount, reason = ma_filter_dca(ctx) or (0, "")
    assert amount == pytest.approx(1500)
    assert "低于250日均线" in reason


def test_drawdown_boost_at_minus_10_percent():
    dates = _trade_dates(40)
    price_df = pd.DataFrame({"trade_date": dates, "close": [100.0] * 40})
    ma250 = pd.Series([100.0] * 40)
    price_drawdown = pd.Series([0.0] * 39 + [-0.11])
    config = BacktestConfig(
        symbol="A500",
        strategy_name="drawdown_boost",
        start_date=dates[0],
        end_date=dates[-1],
        initial_cash=100000,
        fixed_amount=1000,
        frequency="monthly",
    )
    invest_dates = {dates[39]}
    ctx = StrategyContext(
        index=39,
        price_df=price_df,
        ma250=ma250,
        price_drawdown=price_drawdown,
        cash=5000,
        config=config,
        invest_dates=invest_dates,
    )
    amount, reason = drawdown_boost(ctx) or (0, "")
    assert amount == pytest.approx(2000)
    assert "回撤超过10%" in reason


def test_baseline_dca_on_invest_day():
    dates = _trade_dates(10)
    price_df = pd.DataFrame({"trade_date": dates, "close": [10.0] * 10})
    config = BacktestConfig(
        symbol="A500",
        strategy_name="baseline_dca",
        start_date=dates[0],
        end_date=dates[-1],
        initial_cash=10000,
        fixed_amount=1000,
        frequency="monthly",
    )
    invest_dates = build_invest_dates(dates, "monthly")
    ctx = StrategyContext(
        index=0,
        price_df=price_df,
        ma250=pd.Series([None] * 10),
        price_drawdown=pd.Series([0.0] * 10),
        cash=5000,
        config=config,
        invest_dates=invest_dates,
    )
    amount, reason = baseline_dca(ctx) or (0, "")
    assert amount == 1000
    assert reason == "普通定投"
