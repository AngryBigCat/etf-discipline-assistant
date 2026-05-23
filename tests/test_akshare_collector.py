from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from src.collectors.akshare_collector import AkshareCollector, _parse_eastmoney_klines


def test_parse_eastmoney_klines():
    data = {
        "data": {
            "klines": [
                "2024-01-02,1.0,1.1,1.2,0.9,100,1000,0,0,0,0",
                "2024-01-03,1.1,1.2,1.3,1.0,200,2000,0,0,0,0",
            ]
        }
    }
    df = _parse_eastmoney_klines(data)
    assert len(df) == 2
    assert list(df.columns[:7]) == ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]


@patch("src.collectors.akshare_collector.resilient_get_json")
def test_akshare_collector_fetch_history(mock_get_json):
    mock_get_json.return_value = {
        "data": {
            "klines": [
                "2024-01-02,10.0,10.5,10.8,9.8,1000,10000,0,0,0,0",
            ]
        }
    }
    collector = AkshareCollector()
    df = collector.fetch_history("A500", "512050", "2024-01-01", "2024-01-31")
    assert not df.empty
    assert df.iloc[0]["symbol"] == "A500"
    assert df.iloc[0]["trade_date"] == "2024-01-02"
    assert df.iloc[0]["close"] == 10.5


@patch("src.collectors.akshare_collector.resilient_get_json")
def test_akshare_collector_raises_with_network_hint(mock_get_json):
    mock_get_json.side_effect = requests_connection_error()
    collector = AkshareCollector()
    with patch.object(AkshareCollector, "_fetch_sina_history", side_effect=requests_connection_error()):
        with pytest.raises(RuntimeError, match="系统代理|请检查网络"):
            collector.fetch_history("A500", "512050", "2024-01-01", "2024-01-31")


@patch("src.collectors.akshare_collector.resilient_get_json")
def test_akshare_collector_falls_back_to_sina(mock_get_json):
    mock_get_json.side_effect = requests_connection_error()
    sina_df = pd.DataFrame(
        {
            "trade_date": ["2024-11-15", "2024-11-18"],
            "open": [0.982, 0.968],
            "high": [0.988, 0.977],
            "low": [0.964, 0.952],
            "close": [0.966, 0.958],
            "volume": [1000.0, 2000.0],
            "amount": [966.0, 1916.0],
        }
    )
    collector = AkshareCollector()
    with patch.object(AkshareCollector, "_fetch_sina_history", return_value=sina_df):
        df = collector.fetch_history("A500", "512050", "2024-11-01", "2024-11-30")
    assert len(df) == 2
    assert df.iloc[0]["symbol"] == "A500"


def requests_connection_error():
    import requests

    return requests.exceptions.ConnectionError(
        "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))"
    )
