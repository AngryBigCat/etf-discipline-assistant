from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config.settings import get_project_root


def get_assets_seed_path() -> Path:
    env_path = os.getenv("ASSETS_SEED_PATH")
    if env_path:
        path = Path(env_path)
        if not path.is_absolute():
            path = get_project_root() / path
        return path
    return get_project_root() / "config" / "assets.seed.yaml"


@lru_cache
def load_assets_seed() -> list[dict[str, Any]]:
    seed_path = get_assets_seed_path()
    if not seed_path.exists():
        return []

    with seed_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if isinstance(data, list):
        return data
    return list(data.get("assets") or [])


def clear_assets_seed_cache() -> None:
    load_assets_seed.cache_clear()
