from __future__ import annotations

import sqlite3

import pandas as pd
from loguru import logger

BACKTEST_PRICE_COLUMNS = ["symbol", "trade_date", "close"]
# A 股 ETF 单日涨跌幅限制约 10%，留少量缓冲识别脏数据
MAX_ETF_DAILY_CHANGE = 0.12
ROLLING_REF_WINDOW = 20


def _filter_price_outliers(
    df: pd.DataFrame,
    max_daily_change: float = MAX_ETF_DAILY_CHANGE,
    rolling_window: int = ROLLING_REF_WINDOW,
) -> pd.DataFrame:
    """Remove suspiciously low prices (e.g. Sina holiday placeholders).

    Only filters downward anomalies against a rolling median reference.
    Upward moves are kept so legitimate rallies / post-holiday gaps remain.
    """
    if len(df) < 2:
        return df

    work = df.copy().reset_index(drop=True)
    changed = True
    while changed:
        changed = False
        reference = work["close"].shift(1).rolling(rolling_window, min_periods=1).median()
        low_outlier = work["close"] < reference * (1 - max_daily_change)
        low_outlier = low_outlier.fillna(False)
        if low_outlier.any():
            work = work.loc[~low_outlier].reset_index(drop=True)
            changed = True
    return work


def clean_backtest_price_df(
    df: pd.DataFrame,
    *,
    log_filtered: bool = False,
) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return pd.DataFrame(columns=BACKTEST_PRICE_COLUMNS), 0

    raw_count = len(df)
    cleaned = df.copy()
    cleaned["trade_date"] = cleaned["trade_date"].astype(str)
    cleaned["close"] = pd.to_numeric(cleaned["close"], errors="coerce")
    cleaned = cleaned[cleaned["close"].notna()]
    cleaned = cleaned[cleaned["close"] > 0]
    cleaned = cleaned.drop_duplicates(subset=["trade_date"], keep="last")
    cleaned = cleaned.sort_values("trade_date").reset_index(drop=True)
    cleaned = _filter_price_outliers(cleaned)
    cleaned = cleaned[BACKTEST_PRICE_COLUMNS]

    filtered_count = raw_count - len(cleaned)
    if log_filtered and filtered_count > 0:
        logger.warning("已过滤 {} 条无效行情数据。", filtered_count)
    return cleaned, filtered_count


def load_backtest_prices(
    conn: sqlite3.Connection,
    symbol: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    cur = conn.execute(
        """
        SELECT symbol, trade_date, close
        FROM daily_price
        WHERE symbol = ? AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
        """,
        (symbol, start_date, end_date),
    )
    rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=BACKTEST_PRICE_COLUMNS)
    df = pd.DataFrame([dict(row) for row in rows])
    cleaned, _ = clean_backtest_price_df(df, log_filtered=True)
    return cleaned
