from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from src.collectors.akshare_collector import AkshareCollector
from src.collectors.mock_collector import MockCollector
from src.collectors.price_service import CompositeCollector


def _sample_price_df(symbol: str = "KC50") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": [symbol],
            "trade_date": ["2024-03-01"],
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [100.0],
            "amount": [100.0],
        }
    )


def test_mock_collector_returns_data():
    collector = MockCollector()
    df = collector.fetch_history("A500", "512050", "2024-01-01", "2024-06-30")
    assert not df.empty
    assert {"symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"}.issubset(df.columns)
    assert df["symbol"].iloc[0] == "A500"


def test_composite_collector_auto_raises_when_fetch_fails():
    collector = CompositeCollector(mode="auto")

    with patch.object(AkshareCollector, "fetch_history", side_effect=RuntimeError("network error")):
        with pytest.raises(RuntimeError, match="network error"):
            collector.fetch_history("KC50", "588000", "2024-01-01", "2024-03-31")


@patch("src.collectors.akshare_collector.resilient_get_json")
def test_composite_collector_auto_marks_sina_fallback(mock_get_json):
    import requests

    mock_get_json.side_effect = requests.exceptions.ConnectionError("network error")
    sina_df = pd.DataFrame(
        {
            "trade_date": ["2024-03-01"],
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [100.0],
            "amount": [100.0],
        }
    )
    collector = CompositeCollector(mode="auto")
    with patch.object(AkshareCollector, "_fetch_sina_history", return_value=sina_df):
        result = collector.fetch_history("KC50", "588000", "2024-01-01", "2024-03-31")

    assert result.source == "sina"
    assert result.used_fallback is True
    assert not result.df.empty


def test_composite_collector_mock_mode():
    collector = CompositeCollector(mode="mock")
    result = collector.fetch_history("HS300", "510300", "2024-01-01", "2024-02-29")
    assert result.source == "mock"
    assert result.used_fallback is True
    assert not result.df.empty
