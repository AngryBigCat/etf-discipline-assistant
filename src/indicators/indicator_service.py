from __future__ import annotations

from typing import Any

import pandas as pd

from src.indicators.drawdown import compute_drawdowns, resolve_drawdown_used
from src.indicators.moving_average import compute_moving_averages
from src.indicators.volatility import compute_returns, compute_volatility


def _to_optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def compute_indicators(price_df: pd.DataFrame) -> pd.DataFrame:
    if price_df.empty:
        return pd.DataFrame()

    df = price_df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date").reset_index(drop=True)
    close = df["close"].astype(float)

    ma_df = compute_moving_averages(close)
    dd_df = compute_drawdowns(close)
    vol = compute_volatility(close)
    ret_df = compute_returns(close)

    merged = pd.concat([df, ma_df, dd_df, ret_df], axis=1)
    merged["volatility_20d"] = vol
    merged["close_roll_max"] = close.expanding().max()

    rows: list[dict[str, Any]] = []
    history_len = len(merged)
    for _, row in merged.iterrows():
        resolved = resolve_drawdown_used(row, history_len)
        confidence = resolved["confidence_level"]
        if history_len < 250:
            confidence = "low"

        rows.append(
            {
                "symbol": row["symbol"],
                "trade_date": pd.Timestamp(row["trade_date"]).strftime("%Y-%m-%d"),
                "ma20": _to_optional_float(row.get("ma20")),
                "ma60": _to_optional_float(row.get("ma60")),
                "ma120": _to_optional_float(row.get("ma120")),
                "ma250": _to_optional_float(row.get("ma250")),
                "drawdown_60d": _to_optional_float(row.get("drawdown_60d")),
                "drawdown_120d": _to_optional_float(row.get("drawdown_120d")),
                "drawdown_250d": _to_optional_float(row.get("drawdown_250d")),
                "drawdown_used": resolved["drawdown_used"],
                "drawdown_window": resolved["drawdown_window"],
                "volatility_20d": _to_optional_float(row.get("volatility_20d")),
                "return_5d": _to_optional_float(row.get("return_5d")),
                "return_10d": _to_optional_float(row.get("return_10d")),
                "return_20d": _to_optional_float(row.get("return_20d")),
                "confidence_level": confidence,
            }
        )
    return pd.DataFrame(rows)


def compute_indicators_for_symbol(symbol: str, price_df: pd.DataFrame) -> list[dict[str, Any]]:
    if price_df.empty:
        return []
    working = price_df.copy()
    working["symbol"] = symbol
    result = compute_indicators(working)
    return result.to_dict("records")
