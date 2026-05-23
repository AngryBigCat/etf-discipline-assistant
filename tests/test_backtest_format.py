from __future__ import annotations

import math

import pandas as pd
import pytest

from pages.backtest import _format_money, _format_pct


def test_format_pct_returns_dash_for_none():
    assert _format_pct(None) == "—"


def test_format_pct_returns_dash_for_nan():
    assert _format_pct(float("nan")) == "—"


def test_format_pct_formats_valid_value():
    assert _format_pct(0.1234) == "12.34%"


def test_format_money_returns_dash_for_none():
    assert _format_money(None) == "—"


def test_format_money_returns_dash_for_nan():
    assert _format_money(float("nan")) == "—"


def test_format_money_formats_valid_value():
    assert _format_money(1234.5) == "1,234.50"


def test_history_cash_utilization_none_displays_dash():
    value = None
    assert _format_pct(value) == "—"


def test_history_cash_utilization_nan_displays_dash():
    assert _format_pct(math.nan) == "—"
