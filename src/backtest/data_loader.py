from __future__ import annotations

import sqlite3

import pandas as pd


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
        return pd.DataFrame(columns=["symbol", "trade_date", "close"])
    df = pd.DataFrame([dict(row) for row in rows])
    df["trade_date"] = df["trade_date"].astype(str)
    return df
