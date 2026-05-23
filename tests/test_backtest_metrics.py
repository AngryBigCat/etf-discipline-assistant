from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest

from src.backtest.metrics import (
    calculate_annualized_return,
    calculate_average_cost,
    calculate_cash_utilization,
    calculate_max_drawdown,
    calculate_total_return,
)
from src.backtest.models import BacktestDailyState


def test_calculate_total_return():
    assert calculate_total_return(120000, 100000) == pytest.approx(0.2)


def test_calculate_total_return_zero_initial():
    assert calculate_total_return(120000, 0) == 0.0


def test_calculate_annualized_return_short_period():
    assert calculate_annualized_return(110000, 100000, "2026-05-01", "2026-05-20") is None


def test_calculate_annualized_return_long_period():
    value = calculate_annualized_return(120000, 100000, "2025-01-01", "2026-01-01")
    assert value is not None
    assert value > 0


def test_calculate_max_drawdown():
    curve = [
        BacktestDailyState("2026-01-01", 50000, 50000, 100000, 0.0),
        BacktestDailyState("2026-01-02", 50000, 40000, 90000, -0.1),
        BacktestDailyState("2026-01-03", 50000, 36000, 86000, -0.14),
    ]
    assert calculate_max_drawdown(curve) == pytest.approx(-0.14)


def test_calculate_average_cost():
    assert calculate_average_cost(9000, 300) == pytest.approx(30)
    assert calculate_average_cost(9000, 0) == 0.0


def test_calculate_cash_utilization():
    assert calculate_cash_utilization(3000, 10000) == pytest.approx(0.3)
    assert calculate_cash_utilization(1000, 0) == 0.0
