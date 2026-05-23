from __future__ import annotations

import json
import sqlite3

from src.backtest.data_loader import load_backtest_prices, load_multi_symbol_prices
from src.backtest.engine import run_backtest
from src.backtest.models import BacktestConfig, BacktestResult
from src.backtest.portfolio import (
    PORTFOLIO_SYMBOL,
    PortfolioBacktestConfig,
    PortfolioBacktestResult,
    build_portfolio_params_json,
    run_portfolio_backtest,
    validate_portfolio_weights,
)
from src.db.repository import (
    get_backtest_equity_curve,
    get_backtest_positions,
    get_backtest_result,
    get_backtest_run,
    get_backtest_trades,
    save_backtest_equity_curve,
    save_backtest_positions,
    save_backtest_result,
    save_backtest_run,
    save_backtest_trades,
)


def run_and_save_backtest(
    conn: sqlite3.Connection,
    config: BacktestConfig,
) -> tuple[int | None, BacktestResult, str]:
    price_df = load_backtest_prices(conn, config.symbol, config.start_date, config.end_date)
    result = run_backtest(config, price_df)
    if not result.valid:
        return None, result, result.error_message

    run_id = save_backtest_run(
        conn,
        {
            "run_name": config.run_name or "",
            "symbol": config.symbol,
            "strategy_name": config.strategy_name,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "initial_cash": config.initial_cash,
            "fixed_amount": config.fixed_amount,
            "frequency": config.frequency,
            "params_json": json.dumps(config.params, ensure_ascii=False),
        },
    )

    save_backtest_result(
        conn,
        {
            "run_id": run_id,
            "final_value": result.final_value,
            "total_invested": result.total_invested,
            "cash_value": result.cash_value,
            "position_value": result.position_value,
            "total_return": result.total_return,
            "annualized_return": result.annualized_return,
            "max_drawdown": result.max_drawdown,
            "trade_count": result.trade_count,
            "final_quantity": result.final_quantity,
            "average_cost": result.average_cost,
            "actual_start_date": result.actual_start_date,
            "actual_end_date": result.actual_end_date,
            "trading_days": result.trading_days,
            "cash_utilization": result.cash_utilization,
        },
    )

    save_backtest_trades(
        conn,
        [
            {
                "run_id": run_id,
                "trade_date": trade.trade_date,
                "symbol": trade.symbol,
                "action": trade.action,
                "price": trade.price,
                "amount": trade.amount,
                "quantity": trade.quantity,
                "reason": trade.reason,
            }
            for trade in result.trades
        ],
    )

    save_backtest_equity_curve(
        conn,
        [
            {
                "run_id": run_id,
                "trade_date": point.trade_date,
                "cash_value": point.cash_value,
                "position_value": point.position_value,
                "total_value": point.total_value,
                "drawdown": point.drawdown,
            }
            for point in result.equity_curve
        ],
    )

    return run_id, result, "回测已完成"


def run_and_save_portfolio_backtest(
    conn: sqlite3.Connection,
    config: PortfolioBacktestConfig,
) -> tuple[int | None, PortfolioBacktestResult, str]:
    weight_error = validate_portfolio_weights(config.assets)
    if weight_error:
        return None, PortfolioBacktestResult(config=config, valid=False, error_message=weight_error), weight_error

    symbols = [asset.symbol for asset in config.assets]
    load_result = load_multi_symbol_prices(conn, symbols, config.start_date, config.end_date)
    if not load_result.valid:
        return (
            None,
            PortfolioBacktestResult(
                config=config,
                valid=False,
                error_message=load_result.error_message,
                requested_start_date=config.start_date,
                requested_end_date=config.end_date,
                actual_start_date=load_result.actual_start_date,
                actual_end_date=load_result.actual_end_date,
                load_errors=load_result.errors,
            ),
            load_result.error_message,
        )

    result = run_portfolio_backtest(config, load_result.price_dfs, load_result.trade_dates)
    result.load_errors = load_result.errors
    if not result.valid:
        return None, result, result.error_message

    run_id = save_backtest_run(
        conn,
        {
            "run_name": config.run_name or "",
            "symbol": PORTFOLIO_SYMBOL,
            "strategy_name": config.strategy_name,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "initial_cash": config.initial_cash,
            "fixed_amount": config.fixed_amount,
            "frequency": config.frequency,
            "params_json": json.dumps(build_portfolio_params_json(config), ensure_ascii=False),
        },
    )

    save_backtest_result(
        conn,
        {
            "run_id": run_id,
            "final_value": result.final_value,
            "total_invested": result.total_invested,
            "cash_value": result.cash_value,
            "position_value": result.position_value,
            "total_return": result.total_return,
            "annualized_return": result.annualized_return,
            "max_drawdown": result.max_drawdown,
            "trade_count": result.trade_count,
            "final_quantity": 0.0,
            "average_cost": 0.0,
            "actual_start_date": result.actual_start_date,
            "actual_end_date": result.actual_end_date,
            "trading_days": result.trading_days,
            "cash_utilization": result.cash_utilization,
        },
    )

    save_backtest_trades(
        conn,
        [
            {
                "run_id": run_id,
                "trade_date": trade.trade_date,
                "symbol": trade.symbol,
                "action": trade.action,
                "price": trade.price,
                "amount": trade.amount,
                "quantity": trade.quantity,
                "reason": trade.reason,
            }
            for trade in result.trades
        ],
    )

    save_backtest_equity_curve(
        conn,
        [
            {
                "run_id": run_id,
                "trade_date": point.trade_date,
                "cash_value": point.cash_value,
                "position_value": point.position_value,
                "total_value": point.total_value,
                "drawdown": point.drawdown,
            }
            for point in result.equity_curve
        ],
    )

    save_backtest_positions(
        conn,
        [
            {
                "run_id": run_id,
                "symbol": position.symbol,
                "quantity": position.quantity,
                "average_cost": position.average_cost,
                "last_price": position.last_price,
                "market_value": position.market_value,
                "weight": position.weight,
                "target_weight": position.target_weight,
                "deviation": position.deviation,
            }
            for position in result.positions
        ],
    )

    return run_id, result, "组合回测已完成"


def run_backtest_comparison(
    conn: sqlite3.Connection,
    base_config: BacktestConfig,
    strategy_names: list[str],
) -> list[dict]:
    comparison_results: list[dict] = []
    for strategy_name in strategy_names:
        config = BacktestConfig(
            symbol=base_config.symbol,
            strategy_name=strategy_name,
            start_date=base_config.start_date,
            end_date=base_config.end_date,
            initial_cash=base_config.initial_cash,
            fixed_amount=base_config.fixed_amount,
            frequency=base_config.frequency,
            params=dict(base_config.params),
            run_name=base_config.run_name,
        )
        run_id, result, message = run_and_save_backtest(conn, config)
        comparison_results.append(
            {
                "strategy_name": strategy_name,
                "run_id": run_id,
                "result": result,
                "message": message,
            }
        )
    return comparison_results


def load_backtest_detail(conn: sqlite3.Connection, run_id: int) -> dict:
    run = get_backtest_run(conn, run_id)
    if run is None:
        return {}
    return {
        "run": dict(run),
        "result": dict(get_backtest_result(conn, run_id) or {}),
        "trades": [dict(row) for row in get_backtest_trades(conn, run_id)],
        "equity_curve": [dict(row) for row in get_backtest_equity_curve(conn, run_id)],
        "positions": [dict(row) for row in get_backtest_positions(conn, run_id)],
    }
