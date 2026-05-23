from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.config.settings import get_enabled_portfolio_assets
from src.db.repository import (
    get_latest_daily_prices,
    get_latest_indicators,
    list_etf_universe,
    upsert_daily_prices,
    upsert_etf_universe,
    upsert_indicator_rows,
)
from src.db.schema import init_schema


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    upsert_etf_universe(
        conn,
        [
            {
                "symbol": "A500",
                "name": "中证A500ETF",
                "fund_code": "512050",
                "exchange": "SH",
                "enabled": True,
                "enabled_for_signal": True,
            },
            {
                "symbol": "HIDDEN",
                "name": "隐藏标的",
                "fund_code": "999999",
                "exchange": "SH",
                "enabled": False,
                "enabled_for_signal": False,
            },
        ],
    )
    upsert_daily_prices(
        conn,
        pd.DataFrame(
            [
                {
                    "symbol": "A500",
                    "trade_date": "2026-05-22",
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 100,
                    "amount": 100,
                },
                {
                    "symbol": "HIDDEN",
                    "trade_date": "2026-05-22",
                    "open": 2.0,
                    "high": 2.0,
                    "low": 2.0,
                    "close": 2.0,
                    "volume": 100,
                    "amount": 100,
                },
            ]
        ),
    )
    upsert_indicator_rows(
        conn,
        [
            {
                "symbol": "A500",
                "trade_date": "2026-05-22",
                "ma20": None,
                "ma60": None,
                "ma120": None,
                "ma250": None,
                "drawdown_60d": None,
                "drawdown_120d": None,
                "drawdown_250d": None,
                "drawdown_used": None,
                "drawdown_window": None,
                "volatility_20d": None,
                "return_5d": None,
                "return_10d": None,
                "return_20d": None,
                "confidence_level": "normal",
            },
            {
                "symbol": "HIDDEN",
                "trade_date": "2026-05-22",
                "ma20": None,
                "ma60": None,
                "ma120": None,
                "ma250": None,
                "drawdown_60d": None,
                "drawdown_120d": None,
                "drawdown_250d": None,
                "drawdown_used": None,
                "drawdown_window": None,
                "volatility_20d": None,
                "return_5d": None,
                "return_10d": None,
                "return_20d": None,
                "confidence_level": "normal",
            },
        ],
    )
    conn.commit()
    return conn


def test_get_enabled_portfolio_assets_excludes_disabled(memory_conn):
    assets = get_enabled_portfolio_assets(memory_conn)
    symbols = {a["symbol"] for a in assets}
    assert "A500" in symbols
    assert "HIDDEN" not in symbols
    assert "CASH" not in symbols


def test_enabled_only_filters_dashboard_queries(memory_conn):
    universe = list_etf_universe(memory_conn, enabled_only=True)
    assert {row["symbol"] for row in universe} == {"A500"}

    prices = get_latest_daily_prices(memory_conn, enabled_only=True)
    assert set(prices["symbol"]) == {"A500"}

    indicators = get_latest_indicators(memory_conn, enabled_only=True)
    assert set(indicators["symbol"]) == {"A500"}


def test_enabled_only_false_still_returns_all(memory_conn):
    prices = get_latest_daily_prices(memory_conn, enabled_only=False)
    assert set(prices["symbol"]) == {"A500", "HIDDEN"}
