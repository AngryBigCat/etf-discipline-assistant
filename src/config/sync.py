from __future__ import annotations

from typing import Any

import sqlite3

from src.db.repository import get_etf_asset, list_etf_universe, upsert_etf_universe


def sync_assets_from_config(
    conn: sqlite3.Connection,
    config: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, int]:
    assets = config.get("assets") or []
    stats = {"imported": 0, "skipped": 0}
    to_import: list[dict[str, Any]] = []

    for asset in assets:
        symbol = str(asset.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        existing = get_etf_asset(conn, symbol)
        if existing is not None and not force and int(existing["enabled"]) == 0:
            stats["skipped"] += 1
            continue
        to_import.append({**asset, "symbol": symbol})

    stats["imported"] = upsert_etf_universe(conn, to_import) if to_import else 0
    return stats


def sync_assets_to_etf_universe(conn: sqlite3.Connection, config: dict[str, Any]) -> dict[str, Any]:
    assets = config.get("assets") or []
    before_symbols = {row["symbol"] for row in list_etf_universe(conn, enabled_only=False)}

    synced_count = upsert_etf_universe(conn, assets) if assets else 0

    new_symbols: list[str] = []
    new_symbols_with_fund_code: list[str] = []
    for asset in assets:
        symbol = str(asset.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        if symbol not in before_symbols:
            new_symbols.append(symbol)
            fund_code = str(asset.get("fund_code") or "").strip()
            if fund_code:
                new_symbols_with_fund_code.append(symbol)

    return {
        "synced_count": synced_count,
        "symbols": [str(asset.get("symbol") or "").strip().upper() for asset in assets if asset.get("symbol")],
        "new_symbols": new_symbols,
        "new_symbols_with_fund_code": new_symbols_with_fund_code,
    }
