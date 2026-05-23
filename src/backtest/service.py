from __future__ import annotations

import json
import sqlite3

from src.backtest.data_loader import load_backtest_prices
from src.backtest.engine import run_backtest
from src.backtest.models import BacktestConfig, BacktestResult
from src.db.repository import (
    get_backtest_equity_curve,
    get_backtest_result,
    get_backtest_run,
    get_backtest_trades,
    save_backtest_equity_curve,
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


def load_backtest_detail(conn: sqlite3.Connection, run_id: int) -> dict:
    run = get_backtest_run(conn, run_id)
    if run is None:
        return {}
    return {
        "run": dict(run),
        "result": dict(get_backtest_result(conn, run_id) or {}),
        "trades": [dict(row) for row in get_backtest_trades(conn, run_id)],
        "equity_curve": [dict(row) for row in get_backtest_equity_curve(conn, run_id)],
    }
