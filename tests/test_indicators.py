from __future__ import annotations

import pandas as pd

from src.indicators.drawdown import resolve_drawdown_used
from src.indicators.indicator_service import compute_indicators_for_symbol


def test_compute_indicators_full_history():
    rows = []
    for i in range(260):
        rows.append(
            {
                "trade_date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i),
                "open": 1.0 + i * 0.001,
                "high": 1.01 + i * 0.001,
                "low": 0.99 + i * 0.001,
                "close": 1.0 + i * 0.001,
                "volume": 1000,
                "amount": 100000,
            }
        )
    df = pd.DataFrame(rows)
    result = compute_indicators_for_symbol("TEST", df)
    latest = result[-1]
    assert latest["ma250"] is not None
    assert latest["drawdown_250d"] is not None
    assert latest["drawdown_used"] is not None
    assert latest["confidence_level"] == "normal"


def test_compute_indicators_short_history_marks_low_confidence():
    rows = []
    for i in range(30):
        rows.append(
            {
                "trade_date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=i),
                "open": 1.0,
                "high": 1.01,
                "low": 0.99,
                "close": 1.0 + i * 0.001,
                "volume": 1000,
                "amount": 100000,
            }
        )
    df = pd.DataFrame(rows)
    result = compute_indicators_for_symbol("A500", df)
    latest = result[-1]
    assert latest["ma250"] is None
    assert latest["confidence_level"] == "low"
    assert latest["drawdown_used"] is not None


def test_resolve_drawdown_used_prefers_longer_window():
    row = pd.Series(
        {
            "drawdown_250d": -0.08,
            "drawdown_120d": -0.05,
            "drawdown_60d": -0.03,
            "close": 1.0,
        }
    )
    resolved = resolve_drawdown_used(row, history_len=260)
    assert resolved["drawdown_window"] == 250
    assert resolved["drawdown_used"] == -0.08
