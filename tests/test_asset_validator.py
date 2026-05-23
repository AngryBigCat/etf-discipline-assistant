from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from src.assets.validator import (
    compute_implicit_cash_target_weight,
    sum_etf_target_weights,
    validate_asset,
    validate_asset_pool,
)
from src.config.editor import (
    ConfigValidationError,
    backup_config_file,
    format_ai_settings_display,
    load_editable_config,
    save_editable_config,
    validate_editable_config,
)
from src.config.settings import load_settings
from src.config.sync import sync_assets_from_seed
from src.db.repository import list_etf_universe, upsert_etf_universe
from src.db.schema import init_schema


@pytest.fixture
def sample_assets() -> list[dict]:
    return [
        {
            "symbol": "A500",
            "name": "中证A500ETF",
            "fund_code": "512050",
            "exchange": "SH",
            "role": "core",
            "enabled_for_signal": True,
            "target_weight": 0.50,
            "max_weight": 0.65,
            "enabled": True,
        },
        {
            "symbol": "CASH",
            "name": "现金",
            "role": "cash",
            "target_weight": 0.20,
            "enabled_for_signal": False,
            "enabled": True,
        },
    ]


@pytest.fixture
def sample_config(sample_assets: list[dict]) -> dict:
    return {
        "app": {"name": "测试", "base_currency": "CNY"},
        "portfolio": {"total_plan_amount": 100000, "min_cash_position": 0.20},
        "assets": sample_assets,
        "strategy": {"trend": {"ma_short": 20}},
        "actions": {"strong_buy": {"min_score": 80}},
    }


@pytest.fixture
def config_file(tmp_path: Path, sample_config: dict) -> Path:
    path = tmp_path / "config.yaml"
    config_without_assets = {key: value for key, value in sample_config.items() if key != "assets"}
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(config_without_assets, handle, allow_unicode=True, sort_keys=False)
    return path


@pytest.fixture
def memory_conn():
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()


def test_validate_asset_rejects_empty_symbol():
    errors = validate_asset({"symbol": "  "})
    assert any("标的代码不能为空" in error for error in errors)


def test_validate_asset_rejects_duplicate_symbol(sample_assets: list[dict]):
    errors = validate_asset({"symbol": "a500", "name": "重复"}, sample_assets)
    assert any("不能重复" in error for error in errors)


def test_validate_asset_pool_rejects_duplicate_symbols(sample_assets: list[dict]):
    pool = [
        *sample_assets,
        {
            "symbol": "A500",
            "name": "重复",
            "enabled": True,
            "enabled_for_signal": False,
            "target_weight": 0,
            "max_weight": 0,
        },
    ]
    errors = validate_asset_pool(pool)
    assert any("不能重复" in error for error in errors)


def test_validate_asset_pool_rejects_weight_over_100_percent(sample_assets: list[dict]):
    pool = copy.deepcopy(sample_assets)
    pool[0]["target_weight"] = 1.10
    errors = validate_asset_pool(pool)
    assert any("100%" in error for error in errors)


def test_sum_etf_target_weights_excludes_cash_role_and_disabled():
    assets = [
        {"symbol": "A500", "role": "core", "target_weight": 0.50, "enabled": True},
        {"symbol": "MONEY", "role": "cash", "target_weight": 0.20, "enabled": True},
        {"symbol": "OLD", "role": "satellite", "target_weight": 0.30, "enabled": False},
    ]
    assert sum_etf_target_weights(assets) == 0.50
    assert compute_implicit_cash_target_weight(assets) == 0.50


def test_validate_enabled_for_signal_requires_enabled(sample_assets: list[dict]):
    broken = copy.deepcopy(sample_assets)
    broken[0]["enabled"] = False
    broken[0]["enabled_for_signal"] = True
    errors = validate_asset_pool(broken)
    assert any("参与策略信号时必须启用" in error for error in errors)


def test_validate_enabled_for_signal_requires_fund_code(sample_assets: list[dict]):
    broken = copy.deepcopy(sample_assets)
    broken[0]["fund_code"] = ""
    errors = validate_asset_pool(broken)
    assert any("基金代码" in error for error in errors)


def test_disabled_assets_not_counted_in_target_weight_sum(sample_assets: list[dict]):
    pool = copy.deepcopy(sample_assets)
    pool.append(
        {
            "symbol": "OLD",
            "name": "停用标的",
            "role": "satellite",
            "enabled": False,
            "enabled_for_signal": False,
            "target_weight": 0.80,
            "max_weight": 0.80,
        }
    )
    assert validate_asset_pool(pool) == []


def test_load_editable_config_excludes_assets(config_file: Path):
    loaded = load_editable_config(config_path=config_file)
    assert "assets" not in loaded
    assert loaded["portfolio"]["total_plan_amount"] == 100000


def test_validate_editable_config_ignores_assets(sample_config: dict):
    broken = copy.deepcopy(sample_config)
    broken["assets"] = [{"symbol": "", "target_weight": -1}]
    del broken["portfolio"]
    broken["portfolio"] = {"total_plan_amount": 0}
    errors = validate_editable_config({k: v for k, v in broken.items() if k != "assets"})
    assert any("计划总投入" in error for error in errors)
    assert not any("标的" in error for error in errors)


def test_save_editable_config_does_not_write_assets_to_yaml(config_file: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: tmp_path / "backups")

    draft = load_editable_config(config_path=config_file)
    draft["portfolio"]["total_plan_amount"] = 120000

    save_editable_config(draft, config_path=config_file)

    saved = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert saved["portfolio"]["total_plan_amount"] == 120000
    assert "assets" not in saved


def test_save_editable_config_does_not_sync_etf_universe(
    config_file: Path,
    sample_config: dict,
    memory_conn,
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: tmp_path / "backups")
    upsert_etf_universe(memory_conn, sample_config["assets"])
    memory_conn.commit()
    before = memory_conn.execute("SELECT target_weight FROM etf_universe WHERE symbol='A500'").fetchone()[0]

    draft = load_editable_config(config_path=config_file)
    draft["portfolio"]["total_plan_amount"] = 110000
    save_editable_config(draft, config_path=config_file)

    after = memory_conn.execute("SELECT target_weight FROM etf_universe WHERE symbol='A500'").fetchone()[0]
    assert after == before


def test_api_key_not_in_ai_settings_display(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret-should-not-leak")
    display = format_ai_settings_display()
    assert "secret-should-not-leak" not in str(display)


def test_load_assets_seed_contains_default_symbols():
    from src.config.assets_seed import load_assets_seed

    assets = load_assets_seed()
    symbols = {asset["symbol"] for asset in assets}
    assert "A500" in symbols
    assert "CASH" in symbols


def test_project_config_is_loadable():
    settings = load_settings()
    assert settings.get("portfolio")
    assert validate_editable_config(load_editable_config()) == []


def test_sync_assets_from_seed_skips_disabled_without_force(memory_conn, sample_assets: list[dict]):
    upsert_etf_universe(
        memory_conn,
        [{**sample_assets[0], "enabled": False, "target_weight": 0.1}],
    )
    memory_conn.commit()

    stats = sync_assets_from_seed(memory_conn, assets=sample_assets, force=False)
    row = memory_conn.execute("SELECT enabled, target_weight FROM etf_universe WHERE symbol='A500'").fetchone()
    assert stats["skipped"] == 1
    assert row["enabled"] == 0
    assert float(row["target_weight"]) == 0.1


def test_backup_config_file_creates_timestamped_copy(config_file: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: tmp_path / "backups")
    backup_path = backup_config_file(config_path=config_file)
    assert Path(backup_path).exists()


def test_save_does_not_overwrite_when_validation_fails(config_file: Path, monkeypatch):
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: Path("/tmp/unused"))
    original_text = config_file.read_text(encoding="utf-8")
    draft = load_editable_config(config_path=config_file)
    draft["portfolio"]["total_plan_amount"] = -1
    with pytest.raises(ConfigValidationError):
        save_editable_config(draft, config_path=config_file)
    assert config_file.read_text(encoding="utf-8") == original_text
