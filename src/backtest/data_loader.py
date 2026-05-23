from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import pandas as pd
from loguru import logger

BACKTEST_PRICE_COLUMNS = ["symbol", "trade_date", "close"]
# A 股 ETF 单日涨跌幅限制约 10%，留少量缓冲识别脏数据
MAX_ETF_DAILY_CHANGE = 0.12
ROLLING_REF_WINDOW = 20
MIN_MULTI_SYMBOL_TRADING_DAYS = 30


@dataclass
class MultiSymbolPriceLoadResult:
    price_dfs: dict[str, pd.DataFrame] = field(default_factory=dict)
    trade_dates: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    actual_start_date: str = ""
    actual_end_date: str = ""
    valid: bool = False
    error_message: str = ""


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


def load_multi_symbol_prices(
    conn: sqlite3.Connection,
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> MultiSymbolPriceLoadResult:
    result = MultiSymbolPriceLoadResult()
    valid_dfs: dict[str, pd.DataFrame] = {}

    for symbol in symbols:
        df = load_backtest_prices(conn, symbol, start_date, end_date)
        if df.empty:
            message = f"{symbol} 在 {start_date} ~ {end_date} 无有效行情数据"
            result.errors[symbol] = message
            logger.warning(message)
            continue
        valid_dfs[symbol] = df

    if len(valid_dfs) < 2:
        result.error_message = "组合回测至少需要 2 个有效标的的历史行情"
        return result

    actual_start_date = max(str(df.iloc[0]["trade_date"]) for df in valid_dfs.values())
    actual_end_date = min(str(df.iloc[-1]["trade_date"]) for df in valid_dfs.values())
    if actual_start_date > actual_end_date:
        result.error_message = "各标的没有共同可用的历史行情区间"
        return result

    filtered_dfs: dict[str, pd.DataFrame] = {}
    for symbol, df in valid_dfs.items():
        scoped = df[
            (df["trade_date"] >= actual_start_date) & (df["trade_date"] <= actual_end_date)
        ].copy()
        scoped = scoped.sort_values("trade_date").reset_index(drop=True)
        if scoped.empty:
            result.errors[symbol] = f"{symbol} 在共同区间内无有效行情"
            continue
        filtered_dfs[symbol] = scoped

    if len(filtered_dfs) < 2:
        result.error_message = "组合回测至少需要 2 个有效标的的历史行情"
        return result

    common_dates: set[str] | None = None
    for df in filtered_dfs.values():
        dates = set(df["trade_date"].astype(str).tolist())
        common_dates = dates if common_dates is None else common_dates & dates

    trade_dates = sorted(common_dates or [])
    if len(trade_dates) < MIN_MULTI_SYMBOL_TRADING_DAYS:
        result.error_message = (
            f"共同可用交易日不足（当前 {len(trade_dates)} 天，至少需要 "
            f"{MIN_MULTI_SYMBOL_TRADING_DAYS} 天）"
        )
        result.actual_start_date = trade_dates[0] if trade_dates else actual_start_date
        result.actual_end_date = trade_dates[-1] if trade_dates else actual_end_date
        return result

    aligned_dfs: dict[str, pd.DataFrame] = {}
    for symbol, df in filtered_dfs.items():
        aligned = df[df["trade_date"].isin(trade_dates)].copy()
        aligned = aligned.sort_values("trade_date").reset_index(drop=True)
        aligned = aligned[BACKTEST_PRICE_COLUMNS]
        aligned_dfs[symbol] = aligned

    result.price_dfs = aligned_dfs
    result.trade_dates = trade_dates
    result.actual_start_date = trade_dates[0]
    result.actual_end_date = trade_dates[-1]
    result.valid = True
    return result
