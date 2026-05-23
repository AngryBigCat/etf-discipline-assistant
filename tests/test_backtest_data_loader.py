from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.backtest.data_loader import clean_backtest_price_df, load_backtest_prices
from src.db.repository import upsert_daily_prices
from src.db.schema import init_schema


def test_clean_backtest_price_df_filters_non_positive_close():
    df = pd.DataFrame(
        {
            "symbol": ["A500", "A500", "A500"],
            "trade_date": ["2024-01-02", "2024-01-03", "2024-01-04"],
            "close": [10.0, 0.0, -1.0],
        }
    )
    cleaned, filtered_count = clean_backtest_price_df(df)
    assert len(cleaned) == 1
    assert filtered_count == 2
    assert cleaned.iloc[0]["close"] == 10.0


def test_clean_backtest_price_df_filters_empty_close():
    df = pd.DataFrame(
        {
            "symbol": ["A500", "A500", "A500"],
            "trade_date": ["2024-01-02", "2024-01-03", "2024-01-04"],
            "close": [10.0, None, "bad"],
        }
    )
    cleaned, filtered_count = clean_backtest_price_df(df)
    assert len(cleaned) == 1
    assert filtered_count == 2
    assert cleaned.iloc[0]["trade_date"] == "2024-01-02"


def test_clean_backtest_price_df_deduplicates_trade_date_keep_last():
    df = pd.DataFrame(
        {
            "symbol": ["A500", "A500"],
            "trade_date": ["2024-01-02", "2024-01-02"],
            "close": [9.0, 10.0],
        }
    )
    cleaned, filtered_count = clean_backtest_price_df(df)
    assert len(cleaned) == 1
    assert filtered_count == 1
    assert cleaned.iloc[0]["close"] == 10.0


def test_clean_backtest_price_df_returns_empty_when_all_invalid():
    df = pd.DataFrame(
        {
            "symbol": ["A500"],
            "trade_date": ["2024-01-02"],
            "close": [0],
        }
    )
    cleaned, filtered_count = clean_backtest_price_df(df)
    assert cleaned.empty
    assert filtered_count == 1


def test_clean_backtest_price_df_filters_abnormal_daily_jump():
    df = pd.DataFrame(
        {
            "symbol": ["A500"] * 4,
            "trade_date": ["2025-09-30", "2025-10-01", "2025-10-09", "2025-10-10"],
            "close": [1.179, 0.8681, 1.196, 1.180],
        }
    )
    cleaned, filtered_count = clean_backtest_price_df(df)
    assert list(cleaned["trade_date"]) == ["2025-09-30", "2025-10-09", "2025-10-10"]
    assert filtered_count == 1


def test_load_backtest_prices_applies_cleaning(memory_conn):
    price_df = pd.DataFrame(
        {
            "symbol": ["A500", "A500", "A500"],
            "trade_date": ["2024-01-02", "2024-01-03", "2024-01-04"],
            "open": [10.0, 0.0, 11.0],
            "high": [10.0, 0.0, 11.0],
            "low": [10.0, 0.0, 11.0],
            "close": [10.0, 0.0, 11.0],
            "volume": [100.0, 100.0, 100.0],
            "amount": [1000.0, 0.0, 1100.0],
        }
    )
    upsert_daily_prices(memory_conn, price_df)
    loaded = load_backtest_prices(memory_conn, "A500", "2024-01-01", "2024-12-31")
    assert len(loaded) == 2
    assert list(loaded["trade_date"]) == ["2024-01-02", "2024-01-04"]


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn
