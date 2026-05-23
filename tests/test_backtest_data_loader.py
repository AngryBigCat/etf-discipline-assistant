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
            "symbol": ["A500"] * 8,
            "trade_date": [
                "2025-09-29",
                "2025-09-30",
                "2025-10-01",
                "2025-10-02",
                "2025-10-03",
                "2025-10-06",
                "2025-10-09",
                "2025-10-10",
            ],
            "close": [1.543, 1.570, 0.8803, 0.8870, 0.8704, 0.8877, 1.618, 1.528],
        }
    )
    cleaned, filtered_count = clean_backtest_price_df(df)
    assert list(cleaned["trade_date"]) == [
        "2025-09-29",
        "2025-09-30",
        "2025-10-09",
        "2025-10-10",
    ]
    assert filtered_count == 4


def test_clean_backtest_price_df_keeps_post_holiday_first_trading_day():
    df = pd.DataFrame(
        {
            "symbol": ["KC50"] * 4,
            "trade_date": ["2025-09-30", "2025-10-01", "2025-10-09", "2025-10-10"],
            "close": [1.570, 0.8803, 1.618, 1.528],
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


def test_kc50_cleaned_prices_cover_latest_trade_date(memory_conn):
    series = []
    for i in range(30):
        series.append(
            {
                "symbol": "KC50",
                "trade_date": f"2026-04-{i+1:02d}",
                "open": 1.5,
                "high": 1.5,
                "low": 1.5,
                "close": 1.5,
                "volume": 100.0,
                "amount": 150.0,
            }
        )
    series.extend(
        [
            {
                "symbol": "KC50",
                "trade_date": "2026-05-01",
                "open": 0.78,
                "high": 0.78,
                "low": 0.78,
                "close": 0.78,
                "volume": 100.0,
                "amount": 78.0,
            },
            {
                "symbol": "KC50",
                "trade_date": "2026-05-06",
                "open": 1.74,
                "high": 1.74,
                "low": 1.74,
                "close": 1.74,
                "volume": 100.0,
                "amount": 174.0,
            },
            {
                "symbol": "KC50",
                "trade_date": "2026-05-22",
                "open": 1.88,
                "high": 1.88,
                "low": 1.88,
                "close": 1.88,
                "volume": 100.0,
                "amount": 188.0,
            },
        ]
    )
    upsert_daily_prices(memory_conn, pd.DataFrame(series))
    loaded = load_backtest_prices(memory_conn, "KC50", "2026-04-01", "2026-05-22")
    assert str(loaded.iloc[-1]["trade_date"]) == "2026-05-22"
    assert "2026-05-01" not in set(loaded["trade_date"])


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn
