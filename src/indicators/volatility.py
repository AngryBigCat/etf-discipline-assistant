from __future__ import annotations

import pandas as pd


def compute_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    daily_return = close.pct_change()
    if len(close) >= window:
        return daily_return.rolling(window).std()
    return pd.Series(pd.NA, index=close.index)


def compute_returns(close: pd.Series) -> pd.DataFrame:
    result = pd.DataFrame(index=close.index)
    for window, col in [(5, "return_5d"), (10, "return_10d"), (20, "return_20d")]:
        if len(close) > window:
            result[col] = close.pct_change(window)
        else:
            result[col] = pd.NA
    return result
