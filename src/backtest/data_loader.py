from __future__ import annotations

import sqlite3

import pandas as pd
from loguru import logger

BACKTEST_PRICE_COLUMNS = ["symbol", "trade_date", "close"]
# A 股 ETF 单日涨跌幅限制约 10%，留少量缓冲识别脏数据（如节假日错价）
MAX_ETF_DAILY_CHANGE = 0.12


def _filter_price_outliers(
    df: pd.DataFrame,
    max_daily_change: float = MAX_ETF_DAILY_CHANGE,
) -> pd.DataFrame:
    if len(df) < 2:
        return df

    keep = [True] * len(df)
    keep[0] = True
    for index in range(1, len(df)):
        previous_close = None
        for prev_index in range(index - 1, -1, -1):
            if keep[prev_index]:
                previous_close = float(df.iloc[prev_index]["close"])
                break
        if previous_close is None or previous_close <= 0:
            continue
        current_close = float(df.iloc[index]["close"])
        daily_change = abs(current_close / previous_close - 1)
        if daily_change > max_daily_change:
            keep[index] = False
    return df.loc[keep].reset_index(drop=True)


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
