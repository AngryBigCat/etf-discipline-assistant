from __future__ import annotations

import pandas as pd

from src.backtest.metrics import (
    calculate_annualized_return,
    calculate_average_cost,
    calculate_max_drawdown,
    calculate_total_return,
)
from src.backtest.models import BacktestConfig, BacktestDailyState, BacktestResult, BacktestTrade
from src.backtest.strategies import (
    STRATEGY_REGISTRY,
    StrategyContext,
    build_invest_dates,
    precompute_ma250,
    precompute_price_drawdown,
)

MIN_TRADING_DAYS = 30


def _invalid_result(config: BacktestConfig, message: str) -> BacktestResult:
    return BacktestResult(config=config, valid=False, error_message=message)


def run_backtest(config: BacktestConfig, price_df: pd.DataFrame) -> BacktestResult:
    if config.strategy_name not in STRATEGY_REGISTRY:
        return _invalid_result(config, f"未知策略：{config.strategy_name}")

    if price_df.empty:
        return _invalid_result(config, "历史行情数据为空，无法回测")

    if len(price_df) < MIN_TRADING_DAYS:
        return _invalid_result(config, "历史数据不足（少于 30 个交易日）")

    df = price_df.copy()
    df["trade_date"] = df["trade_date"].astype(str)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    trade_dates = df["trade_date"].tolist()
    invest_dates = build_invest_dates(trade_dates, config.frequency)
    ma250 = precompute_ma250(df)
    price_drawdown = precompute_price_drawdown(df)

    cash = float(config.initial_cash)
    quantity = 0.0
    total_invested = 0.0
    peak_value = float(config.initial_cash)
    trades: list[BacktestTrade] = []
    equity_curve: list[BacktestDailyState] = []

    strategy_fn = STRATEGY_REGISTRY[config.strategy_name]

    for index in range(len(df)):
        row = df.iloc[index]
        trade_date = str(row["trade_date"])
        close = float(row["close"]) if pd.notna(row["close"]) else 0.0

        ctx = StrategyContext(
            index=index,
            price_df=df,
            ma250=ma250,
            price_drawdown=price_drawdown,
            cash=cash,
            config=config,
            invest_dates=invest_dates,
        )
        decision = strategy_fn(ctx)
        if decision and close > 0:
            proposed_amount, reason = decision
            amount = min(proposed_amount, cash)
            if amount > 0:
                buy_quantity = amount / close
                cash -= amount
                quantity += buy_quantity
                total_invested += amount
                trades.append(
                    BacktestTrade(
                        trade_date=trade_date,
                        symbol=config.symbol,
                        action="buy",
                        price=close,
                        amount=amount,
                        quantity=buy_quantity,
                        reason=reason,
                    )
                )

        position_value = quantity * close if close > 0 else 0.0
        total_value = cash + position_value
        if total_value > peak_value:
            peak_value = total_value
        drawdown = total_value / peak_value - 1 if peak_value > 0 else 0.0
        equity_curve.append(
            BacktestDailyState(
                trade_date=trade_date,
                cash_value=cash,
                position_value=position_value,
                total_value=total_value,
                drawdown=drawdown,
            )
        )

    final_state = equity_curve[-1]
    final_value = final_state.total_value
    total_return = calculate_total_return(final_value, config.initial_cash)
    annualized_return = calculate_annualized_return(
        final_value,
        config.initial_cash,
        config.start_date,
        config.end_date,
    )

    return BacktestResult(
        config=config,
        final_value=final_value,
        total_invested=total_invested,
        cash_value=final_state.cash_value,
        position_value=final_state.position_value,
        total_return=total_return,
        annualized_return=annualized_return,
        max_drawdown=calculate_max_drawdown(equity_curve),
        trade_count=len(trades),
        final_quantity=quantity,
        average_cost=calculate_average_cost(total_invested, quantity),
        trades=trades,
        equity_curve=equity_curve,
        valid=True,
        error_message="",
    )
