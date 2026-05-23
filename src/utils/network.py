from __future__ import annotations

import socket
import time
import urllib.request
from typing import Any
from urllib.parse import urlparse

import requests
from requests.exceptions import ConnectionError, ProxyError, RequestException, Timeout

EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
DEFAULT_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}


def get_system_proxies() -> dict[str, str]:
    proxies = urllib.request.getproxies()
    result: dict[str, str] = {}
    for key in ("http", "https"):
        value = proxies.get(key)
        if value:
            result[key] = value
    return result


def is_local_proxy_reachable(proxy_url: str, timeout: float = 2.0) -> bool:
    parsed = urlparse(proxy_url)
    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_usable_system_proxies() -> dict[str, str]:
    proxies = get_system_proxies()
    if not proxies:
        return {}
    probe_url = proxies.get("https") or proxies.get("http")
    if probe_url and not is_local_proxy_reachable(probe_url):
        return {}
    return proxies


def is_connection_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, ProxyError, Timeout)):
        return True
    message = str(exc).lower()
    markers = (
        "connection aborted",
        "remote end closed connection",
        "max retries exceeded",
        "unable to connect to proxy",
        "proxyerror",
        "timed out",
        "timeout",
        "connection reset",
        "connection refused",
        "empty reply from server",
    )
    return any(marker in message for marker in markers)


def build_network_hint(exc: BaseException | None = None) -> str:
    proxies = get_system_proxies()
    proxy_value = proxies.get("https") or proxies.get("http")
    parts = ["请检查网络后重试。"]
    if proxy_value:
        parts.insert(
            0,
            f"检测到系统代理 {proxy_value}。请确认代理软件已启动且端口正确；"
            "若在国内可直接访问东方财富，可尝试关闭 Windows 系统代理后再运行。",
        )
    else:
        parts.insert(0, "未检测到系统代理。若当前网络无法直连东方财富，请在 Windows 设置中配置可用代理。")
    if exc is not None and is_connection_error(exc):
        parts.append("也可运行 `python -c \"import urllib.request; print(urllib.request.getproxies())\"` 查看代理配置。")
    return " ".join(parts)


def _request_json(
    url: str,
    params: dict[str, Any] | None,
    *,
    timeout: float,
    trust_env: bool,
    proxies: dict[str, str] | None,
) -> dict[str, Any]:
    session = requests.Session()
    session.trust_env = trust_env
    session.headers.update(DEFAULT_HTTP_HEADERS)
    if proxies:
        session.proxies.update(proxies)
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def resilient_get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float = 20,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> dict[str, Any]:
    system_proxies = get_usable_system_proxies()
    strategies: list[tuple[str, bool, dict[str, str] | None]] = [
        ("direct", False, None),
    ]
    if system_proxies:
        strategies.append(("system_proxy", True, None))
        strategies.append(("explicit_proxy", False, system_proxies))

    last_exc: BaseException | None = None
    for _strategy_name, trust_env, proxies in strategies:
        for attempt in range(max_retries):
            try:
                return _request_json(
                    url,
                    params,
                    timeout=timeout,
                    trust_env=trust_env,
                    proxies=proxies,
                )
            except (ConnectionError, ProxyError, Timeout, RequestException, ValueError) as exc:
                last_exc = exc
                if attempt + 1 < max_retries:
                    time.sleep(retry_delay * (2**attempt))
                    continue
                break
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("请求失败：未知网络错误")
