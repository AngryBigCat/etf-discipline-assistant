from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pandas as pd
import pytest

from src.config.assets_seed import load_assets_seed
from src.config.settings import load_settings
from src.data.backfill import backfill_all_prices, backfill_symbol_prices
from src.db.repository import upsert_etf_universe
from src.db.schema import init_schema


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


@pytest.fixture
def settings():
    return load_settings()


def _sample_price_df(symbol: str = "A500", count: int = 5) -> pd.DataFrame:
    dates = [f"2025-04-0{i}" for i in range(1, count + 1)]
    return pd.DataFrame(
        {
            "symbol": [symbol] * count,
            "trade_date": dates,
            "open": [10.0] * count,
            "high": [10.0] * count,
            "low": [10.0] * count,
            "close": [10.0] * count,
            "volume": [1000.0] * count,
            "amount": [10000.0] * count,
        }
    )


def _seed_universe(conn, settings):
    upsert_etf_universe(conn, load_assets_seed())


@patch("src.data.backfill.AkshareCollector.fetch_history")
def test_backfill_symbol_prices_writes_daily_price(mock_fetch, memory_conn, settings):
    _seed_universe(memory_conn, settings)
    mock_fetch.return_value = _sample_price_df()
    result = backfill_symbol_prices(memory_conn, settings, "A500", "2021-01-01", "2025-04-05")
    assert result.success is True
    assert result.rows == 5
    count = memory_conn.execute("SELECT COUNT(*) FROM daily_price WHERE symbol='A500'").fetchone()[0]
    assert count == 5


@patch("src.data.backfill.AkshareCollector.fetch_history")
def test_backfill_duplicate_does_not_create_duplicates(mock_fetch, memory_conn, settings):
    _seed_universe(memory_conn, settings)
    mock_fetch.return_value = _sample_price_df()
    backfill_symbol_prices(memory_conn, settings, "A500", "2021-01-01", "2025-04-05")
    backfill_symbol_prices(memory_conn, settings, "A500", "2021-01-01", "2025-04-05")
    count = memory_conn.execute("SELECT COUNT(*) FROM daily_price WHERE symbol='A500'").fetchone()[0]
    assert count == 5


@patch("src.data.backfill.AkshareCollector.fetch_history")
def test_backfill_network_error_includes_hint(mock_fetch, memory_conn, settings):
    _seed_universe(memory_conn, settings)
    mock_fetch.side_effect = RuntimeError(
        "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))"
    )
    with patch("src.data.backfill.is_connection_error", return_value=True):
        with patch(
            "src.data.backfill.build_network_hint",
            return_value="请检查网络后重试。",
        ):
            result = backfill_symbol_prices(memory_conn, settings, "A500", "2021-01-01", "2025-04-05")
    assert result.success is False
    assert "请检查网络后重试" in result.message


@patch("src.data.backfill.AkshareCollector.fetch_history")
def test_backfill_all_prices_one_failure_does_not_block_others(mock_fetch, memory_conn, settings):
    _seed_universe(memory_conn, settings)

    def _side_effect(symbol, fund_code, start_date, end_date):
        if symbol == "A500":
            return _sample_price_df("A500")
        raise RuntimeError("AKShare failed")

    mock_fetch.side_effect = _side_effect
    results = backfill_all_prices(memory_conn, settings, "2021-01-01", "2025-04-05")
    assert len(results) >= 2
    assert any(item.symbol == "A500" and item.success for item in results)
    assert any(item.symbol != "A500" and not item.success for item in results)
    a500_count = memory_conn.execute("SELECT COUNT(*) FROM daily_price WHERE symbol='A500'").fetchone()[0]
    assert a500_count == 5
