from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from src.utils.network import (
    build_network_hint,
    get_system_proxies,
    is_connection_error,
    resilient_get_json,
)


def test_is_connection_error_detects_proxy_error():
    exc = requests.exceptions.ProxyError("Unable to connect to proxy")
    assert is_connection_error(exc) is True


def test_is_connection_error_detects_remote_disconnected_message():
    exc = RuntimeError("('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
    assert is_connection_error(exc) is True


def test_build_network_hint_mentions_proxy_when_present():
    with patch("src.utils.network.get_system_proxies", return_value={"https": "http://127.0.0.1:7890"}):
        hint = build_network_hint()
    assert "127.0.0.1:7890" in hint
    assert "系统代理" in hint


def test_build_network_hint_without_proxy():
    with patch("src.utils.network.get_system_proxies", return_value={}):
        hint = build_network_hint()
    assert "未检测到系统代理" in hint


@patch("src.utils.network._request_json")
def test_resilient_get_json_retries_then_succeeds(mock_request):
    mock_request.side_effect = [
        requests.exceptions.ConnectionError("first fail"),
        {"data": {"klines": []}},
    ]
    result = resilient_get_json("https://example.com", {"a": "1"}, max_retries=2, retry_delay=0)
    assert result == {"data": {"klines": []}}
    assert mock_request.call_count == 2


@patch("src.utils.network._request_json")
def test_resilient_get_json_tries_system_proxy_after_direct(mock_request):
    mock_request.side_effect = [
        requests.exceptions.ConnectionError("direct fail"),
        {"data": {"ok": True}},
    ]
    with patch("src.utils.network.get_usable_system_proxies", return_value={"https": "http://127.0.0.1:7890"}):
        result = resilient_get_json("https://example.com", max_retries=1, retry_delay=0)
    assert result == {"data": {"ok": True}}
    assert mock_request.call_count == 2


@patch("src.utils.network.get_system_proxies", return_value={"https": "http://127.0.0.1:7890"})
@patch("src.utils.network.is_local_proxy_reachable", return_value=False)
def test_get_usable_system_proxies_skips_unreachable_proxy(_mock_reachable, _mock_proxies):
    from src.utils.network import get_usable_system_proxies

    assert get_usable_system_proxies() == {}


def test_get_system_proxies_filters_supported_keys():
    with patch("urllib.request.getproxies", return_value={"http": "http://127.0.0.1:7890", "ftp": "x", "no": "*"}):
        assert get_system_proxies() == {"http": "http://127.0.0.1:7890"}
