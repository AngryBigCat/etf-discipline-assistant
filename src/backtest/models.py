from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BacktestConfig:
    symbol: str
    strategy_name: str
    start_date: str
    end_date: str
    initial_cash: float
    fixed_amount: float
    frequency: str
    params: dict[str, Any] = field(default_factory=dict)
    run_name: str = ""


@dataclass
class BacktestTrade:
    trade_date: str
    symbol: str
    action: str
    price: float
    amount: float
    quantity: float
    reason: str


@dataclass
class BacktestDailyState:
    trade_date: str
    cash_value: float
    position_value: float
    total_value: float
    drawdown: float


@dataclass
class BacktestResult:
    config: BacktestConfig
    final_value: float = 0.0
    total_invested: float = 0.0
    cash_value: float = 0.0
    position_value: float = 0.0
    total_return: float = 0.0
    annualized_return: float | None = None
    max_drawdown: float = 0.0
    trade_count: int = 0
    final_quantity: float = 0.0
    average_cost: float = 0.0
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[BacktestDailyState] = field(default_factory=list)
    valid: bool = True
    error_message: str = ""
    requested_start_date: str = ""
    requested_end_date: str = ""
    actual_start_date: str = ""
    actual_end_date: str = ""
    trading_days: int = 0
    cash_utilization: float = 0.0
