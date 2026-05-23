from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from src.backtest.models import BacktestConfig
from src.indicators.moving_average import compute_moving_averages


@dataclass
class StrategyContext:
    index: int
    price_df: pd.DataFrame
    ma250: pd.Series
    price_drawdown: pd.Series
    cash: float
    config: BacktestConfig
    invest_dates: set[str]


StrategyFn = Callable[[StrategyContext], tuple[float, str] | None]


def build_invest_dates(trade_dates: list[str], frequency: str) -> set[str]:
    if not trade_dates:
        return set()
    invest_dates: set[str] = set()
    if frequency == "monthly":
        seen_months: set[tuple[int, int]] = set()
        for trade_date in trade_dates:
            year, month, _ = map(int, trade_date.split("-"))
            key = (year, month)
            if key not in seen_months:
                seen_months.add(key)
                invest_dates.add(trade_date)
    elif frequency == "weekly":
        seen_weeks: set[tuple[int, int]] = set()
        for trade_date in trade_dates:
            dt = pd.Timestamp(trade_date)
            key = (dt.isocalendar().year, dt.isocalendar().week)
            if key not in seen_weeks:
                seen_weeks.add(key)
                invest_dates.add(trade_date)
    return invest_dates


def should_invest_on_date(trade_date: str, frequency: str, invest_dates: set[str]) -> bool:
    if frequency not in {"weekly", "monthly"}:
        return False
    return trade_date in invest_dates


def _apply_cash_limit(amount: float, cash: float) -> float:
    return min(amount, cash)


def baseline_dca(ctx: StrategyContext) -> tuple[float, str] | None:
    trade_date = str(ctx.price_df.iloc[ctx.index]["trade_date"])
    if not should_invest_on_date(trade_date, ctx.config.frequency, ctx.invest_dates):
        return None
    amount = _apply_cash_limit(ctx.config.fixed_amount, ctx.cash)
    if amount <= 0:
        return None
    return amount, "普通定投"


def ma_filter_dca(ctx: StrategyContext) -> tuple[float, str] | None:
    trade_date = str(ctx.price_df.iloc[ctx.index]["trade_date"])
    if not should_invest_on_date(trade_date, ctx.config.frequency, ctx.invest_dates):
        return None
    close = float(ctx.price_df.iloc[ctx.index]["close"])
    ma250 = ctx.ma250.iloc[ctx.index]
    if pd.isna(ma250):
        amount = _apply_cash_limit(ctx.config.fixed_amount, ctx.cash)
        if amount <= 0:
            return None
        return amount, "普通定投"
    multiplier = 1.0 if close >= float(ma250) else 1.5
    amount = _apply_cash_limit(ctx.config.fixed_amount * multiplier, ctx.cash)
    if amount <= 0:
        return None
    reason = "高于250日均线，正常定投" if close >= float(ma250) else "低于250日均线，提高定投金额"
    return amount, reason


def drawdown_boost(ctx: StrategyContext) -> tuple[float, str] | None:
    trade_date = str(ctx.price_df.iloc[ctx.index]["trade_date"])
    if not should_invest_on_date(trade_date, ctx.config.frequency, ctx.invest_dates):
        return None
    drawdown = ctx.price_drawdown.iloc[ctx.index]
    if pd.isna(drawdown):
        multiplier = 1.0
        reason = "普通定投"
    elif drawdown <= -0.15:
        multiplier = 3.0
        reason = "回撤超过15%，提高买入金额"
    elif drawdown <= -0.10:
        multiplier = 2.0
        reason = "回撤超过10%，提高买入金额"
    elif drawdown <= -0.05:
        multiplier = 1.5
        reason = "回撤超过5%，提高买入金额"
    else:
        multiplier = 1.0
        reason = "普通定投"
    amount = _apply_cash_limit(ctx.config.fixed_amount * multiplier, ctx.cash)
    if amount <= 0:
        return None
    return amount, reason


STRATEGY_REGISTRY: dict[str, StrategyFn] = {
    "baseline_dca": baseline_dca,
    "ma_filter_dca": ma_filter_dca,
    "drawdown_boost": drawdown_boost,
}


def precompute_ma250(price_df: pd.DataFrame) -> pd.Series:
    close = pd.to_numeric(price_df["close"], errors="coerce")
    ma_df = compute_moving_averages(close)
    return ma_df["ma250"]


def precompute_price_drawdown(price_df: pd.DataFrame) -> pd.Series:
    close = pd.to_numeric(price_df["close"], errors="coerce")
    peak = close.cummax()
    return close / peak - 1
