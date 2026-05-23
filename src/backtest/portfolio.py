from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.backtest.metrics import (
    calculate_annualized_return,
    calculate_cash_utilization,
    calculate_max_drawdown,
    calculate_total_return,
)
from src.backtest.models import BacktestDailyState, BacktestTrade
from src.backtest.strategies import build_invest_dates

MIN_TRADING_DAYS = 30
PORTFOLIO_SYMBOL = "PORTFOLIO"
PORTFOLIO_STRATEGIES = {"portfolio_dca", "portfolio_rebalance"}


@dataclass
class PortfolioAssetConfig:
    symbol: str
    target_weight: float


@dataclass
class PortfolioBacktestConfig:
    assets: list[PortfolioAssetConfig]
    start_date: str
    end_date: str
    initial_cash: float
    fixed_amount: float
    frequency: str
    strategy_name: str
    rebalance_threshold: float = 0.05
    run_name: str = ""


@dataclass
class PortfolioPosition:
    symbol: str
    quantity: float
    average_cost: float
    last_price: float
    market_value: float
    weight: float
    target_weight: float
    deviation: float


@dataclass
class PortfolioBacktestResult:
    config: PortfolioBacktestConfig
    final_value: float = 0.0
    cash_value: float = 0.0
    position_value: float = 0.0
    total_invested: float = 0.0
    total_return: float = 0.0
    annualized_return: float | None = None
    max_drawdown: float = 0.0
    trade_count: int = 0
    cash_utilization: float = 0.0
    positions: list[PortfolioPosition] = field(default_factory=list)
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[BacktestDailyState] = field(default_factory=list)
    valid: bool = True
    error_message: str = ""
    requested_start_date: str = ""
    requested_end_date: str = ""
    actual_start_date: str = ""
    actual_end_date: str = ""
    trading_days: int = 0
    load_errors: dict[str, str] = field(default_factory=dict)


def validate_portfolio_weights(assets: list[PortfolioAssetConfig]) -> str | None:
    if len(assets) < 2:
        return "组合回测至少需要 2 个标的"
    total_weight = sum(asset.target_weight for asset in assets)
    if total_weight > 1.0 + 1e-9:
        return f"ETF 目标权重合计 {total_weight * 100:.2f}% 超过 100%，请调整后再运行"
    for asset in assets:
        if asset.target_weight <= 0:
            return f"标的 {asset.symbol} 的目标权重必须大于 0"
    return None


def cash_target_weight(assets: list[PortfolioAssetConfig]) -> float:
    total = sum(asset.target_weight for asset in assets)
    return max(0.0, 1.0 - total)


def build_portfolio_params_json(config: PortfolioBacktestConfig) -> dict[str, Any]:
    return {
        "portfolio_assets": [
            {"symbol": asset.symbol, "target_weight": asset.target_weight}
            for asset in config.assets
        ],
        "cash_target_weight": cash_target_weight(config.assets),
        "rebalance_threshold": config.rebalance_threshold,
    }


def _build_month_end_dates(trade_dates: list[str]) -> set[str]:
    last_by_month: dict[tuple[int, int], str] = {}
    for trade_date in trade_dates:
        year, month, _ = map(int, trade_date.split("-"))
        last_by_month[(year, month)] = trade_date
    return set(last_by_month.values())


def _compute_position_value(
    quantities: dict[str, float],
    closes: dict[str, float],
) -> float:
    return sum(quantities[symbol] * closes[symbol] for symbol in quantities)


def _execute_buy(
    *,
    trade_date: str,
    symbol: str,
    amount: float,
    close: float,
    cash: float,
    quantities: dict[str, float],
    average_costs: dict[str, float],
    reason: str,
) -> tuple[float, BacktestTrade | None]:
    amount = min(amount, cash)
    if amount <= 0 or close <= 0:
        return cash, None
    buy_quantity = amount / close
    old_quantity = quantities[symbol]
    old_cost = average_costs[symbol]
    new_quantity = old_quantity + buy_quantity
    if new_quantity > 0:
        average_costs[symbol] = (
            (old_quantity * old_cost + amount) / new_quantity if old_quantity > 0 else amount / buy_quantity
        )
    quantities[symbol] = new_quantity
    cash -= amount
    return cash, BacktestTrade(
        trade_date=trade_date,
        symbol=symbol,
        action="buy",
        price=close,
        amount=amount,
        quantity=buy_quantity,
        reason=reason,
    )


def _execute_sell(
    *,
    trade_date: str,
    symbol: str,
    sell_quantity: float,
    close: float,
    cash: float,
    quantities: dict[str, float],
    reason: str,
) -> tuple[float, BacktestTrade | None]:
    sell_quantity = min(sell_quantity, quantities[symbol])
    if sell_quantity <= 0 or close <= 0:
        return cash, None
    amount = sell_quantity * close
    quantities[symbol] -= sell_quantity
    cash += amount
    return cash, BacktestTrade(
        trade_date=trade_date,
        symbol=symbol,
        action="sell",
        price=close,
        amount=amount,
        quantity=sell_quantity,
        reason=reason,
    )


def _run_dca_buys(
    *,
    trade_date: str,
    config: PortfolioBacktestConfig,
    closes: dict[str, float],
    cash: float,
    quantities: dict[str, float],
    average_costs: dict[str, float],
) -> tuple[float, list[BacktestTrade]]:
    trades: list[BacktestTrade] = []
    etf_weight_sum = sum(asset.target_weight for asset in config.assets)
    if etf_weight_sum <= 0:
        return cash, trades

    invest_amount = min(config.fixed_amount, cash)
    if invest_amount <= 0:
        return cash, trades

    for asset in config.assets:
        alloc_amount = invest_amount * (asset.target_weight / etf_weight_sum)
        close = closes[asset.symbol]
        cash, trade = _execute_buy(
            trade_date=trade_date,
            symbol=asset.symbol,
            amount=alloc_amount,
            close=close,
            cash=cash,
            quantities=quantities,
            average_costs=average_costs,
            reason="组合定投，按目标权重买入",
        )
        if trade is not None:
            trades.append(trade)
    return cash, trades


def _run_rebalance(
    *,
    trade_date: str,
    config: PortfolioBacktestConfig,
    closes: dict[str, float],
    cash: float,
    quantities: dict[str, float],
    average_costs: dict[str, float],
) -> tuple[float, list[BacktestTrade]]:
    trades: list[BacktestTrade] = []
    position_value = _compute_position_value(quantities, closes)
    total_value = cash + position_value
    if total_value <= 0:
        return cash, trades

    threshold = config.rebalance_threshold

    for asset in config.assets:
        close = closes[asset.symbol]
        current_value = quantities[asset.symbol] * close
        current_weight = current_value / total_value
        target_weight = asset.target_weight
        deviation = current_weight - target_weight
        target_value = target_weight * total_value

        if deviation > threshold:
            sell_value = current_value - target_value
            sell_quantity = sell_value / close if close > 0 else 0.0
            cash, trade = _execute_sell(
                trade_date=trade_date,
                symbol=asset.symbol,
                sell_quantity=sell_quantity,
                close=close,
                cash=cash,
                quantities=quantities,
                reason="组合再平衡，权重偏离超过阈值",
            )
            if trade is not None:
                trades.append(trade)

    position_value = _compute_position_value(quantities, closes)
    total_value = cash + position_value
    if total_value <= 0:
        return cash, trades

    for asset in config.assets:
        close = closes[asset.symbol]
        current_value = quantities[asset.symbol] * close
        current_weight = current_value / total_value
        target_weight = asset.target_weight
        deviation = current_weight - target_weight
        target_value = target_weight * total_value

        if deviation < -threshold and cash > 0:
            buy_value = min(cash, target_value - current_value)
            cash, trade = _execute_buy(
                trade_date=trade_date,
                symbol=asset.symbol,
                amount=buy_value,
                close=close,
                cash=cash,
                quantities=quantities,
                average_costs=average_costs,
                reason="组合再平衡，权重偏离超过阈值",
            )
            if trade is not None:
                trades.append(trade)

    return cash, trades


def _build_final_positions(
    config: PortfolioBacktestConfig,
    quantities: dict[str, float],
    average_costs: dict[str, float],
    closes: dict[str, float],
    cash: float,
) -> list[PortfolioPosition]:
    position_value = _compute_position_value(quantities, closes)
    total_value = cash + position_value
    positions: list[PortfolioPosition] = []
    for asset in config.assets:
        close = closes[asset.symbol]
        quantity = quantities[asset.symbol]
        market_value = quantity * close
        weight = market_value / total_value if total_value > 0 else 0.0
        positions.append(
            PortfolioPosition(
                symbol=asset.symbol,
                quantity=quantity,
                average_cost=average_costs[asset.symbol],
                last_price=close,
                market_value=market_value,
                weight=weight,
                target_weight=asset.target_weight,
                deviation=weight - asset.target_weight,
            )
        )
    return positions


def run_portfolio_backtest(
    config: PortfolioBacktestConfig,
    price_dfs: dict[str, pd.DataFrame],
    trade_dates: list[str],
) -> PortfolioBacktestResult:
    weight_error = validate_portfolio_weights(config.assets)
    if weight_error:
        return PortfolioBacktestResult(
            config=config,
            valid=False,
            error_message=weight_error,
            requested_start_date=config.start_date,
            requested_end_date=config.end_date,
        )

    if config.strategy_name not in PORTFOLIO_STRATEGIES:
        return PortfolioBacktestResult(
            config=config,
            valid=False,
            error_message=f"未知组合策略：{config.strategy_name}",
            requested_start_date=config.start_date,
            requested_end_date=config.end_date,
        )

    if len(trade_dates) < MIN_TRADING_DAYS:
        return PortfolioBacktestResult(
            config=config,
            valid=False,
            error_message="历史数据不足（少于 30 个交易日）",
            requested_start_date=config.start_date,
            requested_end_date=config.end_date,
            actual_start_date=trade_dates[0] if trade_dates else "",
            actual_end_date=trade_dates[-1] if trade_dates else "",
            trading_days=len(trade_dates),
        )

    symbols = [asset.symbol for asset in config.assets]
    invest_dates = build_invest_dates(trade_dates, config.frequency)
    month_end_dates = _build_month_end_dates(trade_dates)
    price_map = {
        symbol: dict(zip(price_dfs[symbol]["trade_date"].astype(str), price_dfs[symbol]["close"]))
        for symbol in symbols
    }

    cash = float(config.initial_cash)
    quantities = {symbol: 0.0 for symbol in symbols}
    average_costs = {symbol: 0.0 for symbol in symbols}
    total_invested = 0.0
    peak_value = float(config.initial_cash)
    trades: list[BacktestTrade] = []
    equity_curve: list[BacktestDailyState] = []

    for trade_date in trade_dates:
        closes = {symbol: float(price_map[symbol][trade_date]) for symbol in symbols}

        if trade_date in invest_dates:
            cash, dca_trades = _run_dca_buys(
                trade_date=trade_date,
                config=config,
                closes=closes,
                cash=cash,
                quantities=quantities,
                average_costs=average_costs,
            )
            for trade in dca_trades:
                total_invested += trade.amount
            trades.extend(dca_trades)

        if config.strategy_name == "portfolio_rebalance" and trade_date in month_end_dates:
            cash, rebalance_trades = _run_rebalance(
                trade_date=trade_date,
                config=config,
                closes=closes,
                cash=cash,
                quantities=quantities,
                average_costs=average_costs,
            )
            for trade in rebalance_trades:
                if trade.action == "buy":
                    total_invested += trade.amount
            trades.extend(rebalance_trades)

        position_value = _compute_position_value(quantities, closes)
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

    if not equity_curve:
        return PortfolioBacktestResult(
            config=config,
            valid=False,
            error_message="历史行情数据为空，无法回测",
            requested_start_date=config.start_date,
            requested_end_date=config.end_date,
        )

    final_closes = {
        symbol: float(price_dfs[symbol].iloc[-1]["close"])
        for symbol in symbols
    }
    final_state = equity_curve[-1]
    positions = _build_final_positions(config, quantities, average_costs, final_closes, cash)
    actual_start_date = trade_dates[0]
    actual_end_date = trade_dates[-1]

    return PortfolioBacktestResult(
        config=config,
        final_value=final_state.total_value,
        cash_value=final_state.cash_value,
        position_value=final_state.position_value,
        total_invested=total_invested,
        total_return=calculate_total_return(final_state.total_value, config.initial_cash),
        annualized_return=calculate_annualized_return(
            final_state.total_value,
            config.initial_cash,
            actual_start_date,
            actual_end_date,
        ),
        max_drawdown=calculate_max_drawdown(equity_curve),
        trade_count=len(trades),
        cash_utilization=calculate_cash_utilization(total_invested, config.initial_cash),
        positions=positions,
        trades=trades,
        equity_curve=equity_curve,
        valid=True,
        requested_start_date=config.start_date,
        requested_end_date=config.end_date,
        actual_start_date=actual_start_date,
        actual_end_date=actual_end_date,
        trading_days=len(trade_dates),
    )
