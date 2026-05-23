from __future__ import annotations

import os
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from loguru import logger

from src.assets.queries import (
    list_enabled_portfolio_assets as _list_enabled_portfolio_assets,
    list_signal_assets as _list_signal_assets,
    list_watch_only_assets as _list_watch_only_assets,
)

load_dotenv()


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_config_path() -> Path:
    env_path = os.getenv("CONFIG_PATH")
    if env_path:
        path = Path(env_path)
        if not path.is_absolute():
            path = get_project_root() / path
        return path

    default_path = get_project_root() / "config" / "app.yaml"
    legacy_path = get_project_root() / "config.yaml"
    if default_path.exists():
        return default_path
    if legacy_path.exists():
        logger.warning(
            "根目录 config.yaml 已弃用，请迁移到 config/app.yaml"
        )
        return legacy_path
    return default_path


def get_database_path() -> Path:
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        path = Path(env_path)
        if not path.is_absolute():
            path = get_project_root() / path
        return path
    return get_project_root() / "data" / "etf_assistant.db"


def get_price_data_source() -> str:
    return os.getenv("PRICE_DATA_SOURCE", "auto").lower()


def get_llm_settings() -> dict[str, Any]:
    return {
        "provider": (os.getenv("LLM_PROVIDER") or "mock").lower(),
        "api_key": os.getenv("LLM_API_KEY") or "",
        "api_base": os.getenv("LLM_API_BASE") or "",
        "model": os.getenv("LLM_MODEL") or "",
        "timeout": int(os.getenv("LLM_TIMEOUT") or 30),
    }


@lru_cache
def load_settings() -> dict[str, Any]:
    config_path = get_config_path()
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clear_settings_cache() -> None:
    load_settings.cache_clear()


def get_tradeable_assets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    assets = _list_enabled_portfolio_assets(conn)
    return [
        asset
        for asset in assets
        if str(asset.get("fund_code") or "").strip()
    ]


def get_enabled_portfolio_assets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """enabled=true ETF assets for portfolio entry (excludes CASH)."""
    return _list_enabled_portfolio_assets(conn)


def get_signal_assets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """enabled=true, enabled_for_signal=true, excludes CASH."""
    return _list_signal_assets(conn)


def get_watch_only_assets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """enabled=true, enabled_for_signal=false, excludes CASH."""
    return _list_watch_only_assets(conn)
