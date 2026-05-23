from __future__ import annotations

from datetime import datetime

from src.backtest.models import BacktestDailyState


def calculate_total_return(final_value: float, initial_cash: float) -> float:
    if initial_cash <= 0:
        return 0.0
    return (final_value - initial_cash) / initial_cash


def calculate_annualized_return(
    final_value: float,
    initial_cash: float,
    start_date: str,
    end_date: str,
) -> float | None:
    if initial_cash <= 0 or final_value <= 0:
        return None
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end - start).days
    if days < 30:
        return None
    return (final_value / initial_cash) ** (365 / days) - 1


def calculate_max_drawdown(equity_curve: list[BacktestDailyState]) -> float:
    if not equity_curve:
        return 0.0
    return min(point.drawdown for point in equity_curve)


def calculate_average_cost(total_invested: float, final_quantity: float) -> float:
    if final_quantity <= 0:
        return 0.0
    return total_invested / final_quantity
