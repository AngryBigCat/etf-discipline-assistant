from __future__ import annotations

from unittest.mock import patch

from src.collectors.akshare_collector import AkshareCollector
from src.collectors.mock_collector import MockCollector
from src.collectors.price_service import CompositeCollector


def test_mock_collector_returns_data():
    collector = MockCollector()
    df = collector.fetch_history("A500", "512050", "2024-01-01", "2024-06-30")
    assert not df.empty
    assert {"symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"}.issubset(df.columns)
    assert df["symbol"].iloc[0] == "A500"


def test_composite_collector_falls_back_to_mock():
    collector = CompositeCollector(mode="auto")

    def _fail(*args, **kwargs):
        raise RuntimeError("network error")

    with patch.object(AkshareCollector, "fetch_history", side_effect=_fail):
        result = collector.fetch_history("KC50", "588000", "2024-01-01", "2024-03-31")

    assert result.used_fallback is True
    assert result.source == "mock"
    assert not result.df.empty


def test_composite_collector_mock_mode():
    collector = CompositeCollector(mode="mock")
    result = collector.fetch_history("HS300", "510300", "2024-01-01", "2024-02-29")
    assert result.source == "mock"
    assert result.used_fallback is True
    assert not result.df.empty
