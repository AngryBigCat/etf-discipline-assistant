from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config.assets_seed import get_assets_seed_path, load_assets_seed
from src.config.editor import load_editable_config, save_editable_config
from src.config.settings import clear_settings_cache, get_config_path, get_project_root, load_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_default_config_path_points_to_config_app_yaml(monkeypatch):
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    assert get_config_path() == get_project_root() / "config" / "app.yaml"


def test_config_path_resolves_relative_env_path(tmp_path, monkeypatch):
    relative = Path("custom") / "app.yaml"
    config_path = tmp_path / relative
    config_path.parent.mkdir(parents=True)
    config_path.write_text("portfolio:\n  total_plan_amount: 1\n", encoding="utf-8")

    monkeypatch.setenv("CONFIG_PATH", str(relative))
    monkeypatch.setattr("src.config.settings.get_project_root", lambda: tmp_path)

    assert get_config_path() == config_path


def test_config_path_resolves_absolute_env_path(tmp_path, monkeypatch):
    config_path = tmp_path / "absolute_app.yaml"
    config_path.write_text("portfolio:\n  total_plan_amount: 1\n", encoding="utf-8")

    monkeypatch.setenv("CONFIG_PATH", str(config_path))

    assert get_config_path() == config_path


def test_config_path_prefers_project_env_over_stale_process_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("CONFIG_PATH=config/app.yaml\n", encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH", "config.yaml")
    monkeypatch.setattr("src.config.settings.get_project_root", lambda: tmp_path)

    from src.config.settings import _load_project_env, get_config_path

    _load_project_env()

    assert get_config_path() == tmp_path / "config" / "app.yaml"


def test_load_settings_reads_config_app_yaml(monkeypatch):
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    settings = load_settings()
    assert settings.get("portfolio", {}).get("total_plan_amount") == 100000.0
    assert "assets" not in settings


def test_save_editable_config_writes_config_app_yaml(tmp_path, monkeypatch):
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    app_path = tmp_path / "config" / "app.yaml"
    app_path.parent.mkdir(parents=True)
    app_path.write_text(
        yaml.dump({"portfolio": {"total_plan_amount": 100000}}, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.config.settings.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: tmp_path / "backups")

    draft = load_editable_config()
    draft["portfolio"]["total_plan_amount"] = 120000
    save_editable_config(draft)

    saved = yaml.safe_load(app_path.read_text(encoding="utf-8"))
    assert saved["portfolio"]["total_plan_amount"] == 120000
    assert "assets" not in saved


def test_assets_seed_path_is_independent_from_app_config(monkeypatch):
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    assert get_assets_seed_path() == get_project_root() / "config" / "assets.seed.yaml"
    assets = load_assets_seed()
    assert assets
    assert get_config_path().name == "app.yaml"
