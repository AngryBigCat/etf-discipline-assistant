from __future__ import annotations

import sqlite3
from typing import Any

from src.db.repository import list_etf_universe, list_signal_enabled_etfs


def row_to_asset(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    return {
        "symbol": data.get("symbol"),
        "name": data.get("name"),
        "fund_code": data.get("fund_code") or "",
        "exchange": data.get("exchange") or "",
        "index_code": data.get("index_code") or "",
        "role": data.get("role"),
        "market": data.get("market"),
        "risk_level": data.get("risk_level", 3),
        "target_weight": float(data.get("target_weight") or 0),
        "max_weight": float(data.get("max_weight") or 0),
        "min_weight": float(data.get("min_weight") or 0),
        "single_buy_ratio": float(data.get("single_buy_ratio") or 0),
        "enabled": bool(data.get("enabled", 1)),
        "enabled_for_signal": bool(data.get("enabled_for_signal", 0)),
    }


def list_all_assets(conn: sqlite3.Connection, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    return [row_to_asset(row) for row in list_etf_universe(conn, enabled_only=enabled_only)]


def list_enabled_portfolio_assets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        asset
        for asset in list_all_assets(conn, enabled_only=True)
        if asset.get("symbol") != "CASH" and asset.get("role") != "cash"
    ]


def list_signal_assets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [row_to_asset(row) for row in list_signal_enabled_etfs(conn)]


def list_watch_only_assets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for asset in list_all_assets(conn, enabled_only=True):
        if asset.get("symbol") == "CASH" or asset.get("role") == "cash":
            continue
        if asset.get("enabled_for_signal"):
            continue
        assets.append(asset)
    return assets
