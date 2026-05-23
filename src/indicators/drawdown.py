from __future__ import annotations

from typing import Any

import pandas as pd


def compute_drawdowns(close: pd.Series) -> pd.DataFrame:
    result = pd.DataFrame(index=close.index)
    for window, col in [(60, "drawdown_60d"), (120, "drawdown_120d"), (250, "drawdown_250d")]:
        if len(close) >= window:
            rolling_max = close.rolling(window).max()
            result[col] = close / rolling_max - 1
        else:
            result[col] = pd.NA
    return result


def resolve_drawdown_used(row: pd.Series, history_len: int) -> dict[str, Any]:
    for window, col in [(250, "drawdown_250d"), (120, "drawdown_120d"), (60, "drawdown_60d")]:
        value = row.get(col)
        if history_len >= window and pd.notna(value):
            confidence = "normal" if window >= 120 else "low"
            return {
                "drawdown_used": float(value),
                "drawdown_window": window,
                "confidence_level": confidence,
            }

    if history_len >= 2:
        rolling_max = float(row.get("close_roll_max", row.get("close", 0)))
        close_val = float(row.get("close", 0))
        if rolling_max > 0:
            return {
                "drawdown_used": close_val / rolling_max - 1,
                "drawdown_window": history_len,
                "confidence_level": "low",
            }

    return {
        "drawdown_used": None,
        "drawdown_window": None,
        "confidence_level": "low",
    }
