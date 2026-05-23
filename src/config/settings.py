from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

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
    return get_project_root() / "config.yaml"


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


@lru_cache
def load_settings() -> dict[str, Any]:
    config_path = get_config_path()
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_tradeable_assets(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = settings or load_settings()
    assets: list[dict[str, Any]] = []
    for asset in cfg.get("assets", []):
        if not asset.get("enabled", True):
            continue
        fund_code = (asset.get("fund_code") or "").strip()
        if not fund_code:
            continue
        assets.append(asset)
    return assets


def get_enabled_portfolio_assets(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """enabled=true ETF assets for portfolio entry (excludes CASH)."""
    cfg = settings or load_settings()
    assets: list[dict[str, Any]] = []
    for asset in cfg.get("assets", []):
        if not asset.get("enabled", True):
            continue
        if asset.get("symbol") == "CASH":
            continue
        assets.append(asset)
    return assets


def get_signal_assets(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """enabled=true, enabled_for_signal=true, excludes CASH."""
    cfg = settings or load_settings()
    assets: list[dict[str, Any]] = []
    for asset in cfg.get("assets", []):
        if not asset.get("enabled", True):
            continue
        if asset.get("symbol") == "CASH":
            continue
        if not asset.get("enabled_for_signal", True):
            continue
        assets.append(asset)
    return assets


def get_watch_only_assets(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """enabled=true, enabled_for_signal=false, excludes CASH."""
    cfg = settings or load_settings()
    assets: list[dict[str, Any]] = []
    for asset in cfg.get("assets", []):
        if not asset.get("enabled", True):
            continue
        if asset.get("symbol") == "CASH":
            continue
        if asset.get("enabled_for_signal", True):
            continue
        assets.append(asset)
    return assets
