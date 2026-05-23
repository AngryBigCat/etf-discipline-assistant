from __future__ import annotations

from typing import Any

import sqlite3

from src.config.assets_seed import load_assets_seed
from src.db.repository import get_etf_asset, upsert_etf_universe


def sync_assets_from_seed(
    conn: sqlite3.Connection,
    *,
    assets: list[dict[str, Any]] | None = None,
    force: bool = False,
) -> dict[str, int]:
    asset_list = assets if assets is not None else load_assets_seed()
    stats = {"imported": 0, "skipped": 0}
    to_import: list[dict[str, Any]] = []

    for asset in asset_list:
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


def sync_assets_from_config(
    conn: sqlite3.Connection,
    config: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, int]:
    """兼容旧接口：优先使用 config['assets']，否则回退到 assets.seed.yaml。"""
    assets = config.get("assets") or load_assets_seed()
    return sync_assets_from_seed(conn, assets=assets, force=force)
