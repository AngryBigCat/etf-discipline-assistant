from __future__ import annotations

import pandas as pd


def compute_moving_averages(close: pd.Series) -> pd.DataFrame:
    result = pd.DataFrame(index=close.index)
    for window, col in [(20, "ma20"), (60, "ma60"), (120, "ma120"), (250, "ma250")]:
        if len(close) >= window:
            result[col] = close.rolling(window).mean()
        else:
            result[col] = pd.NA
    return result
