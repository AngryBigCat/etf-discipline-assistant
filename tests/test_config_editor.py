from __future__ import annotations

import copy
from pathlib import Path

import sqlite3

import pytest
import yaml

from src.config.editor import (
    ConfigValidationError,
    backup_config_file,
    format_ai_settings_display,
    load_editable_config,
    save_editable_config,
    validate_editable_config,
)
from src.config.settings import load_settings
from src.db.repository import upsert_etf_universe, upsert_strategy_signals
from src.db.schema import init_schema


@pytest.fixture
def sample_config() -> dict:
    return {
        "app": {"name": "测试", "base_currency": "CNY"},
        "portfolio": {
            "total_plan_amount": 100000,
            "min_cash_position": 0.20,
        },
        "assets": [
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
        ],
        "strategy": {
            "trend": {"ma_short": 20, "ma_mid": 60, "ma_long": 120, "ma_year": 250},
            "drawdown": {"small_buy_threshold": -0.03},
        },
        "actions": {
            "strong_buy": {"min_score": 80},
            "small_buy": {"min_score": 65},
            "hold": {"min_score": 35},
            "stop_buy": {"min_score": 0},
        },
    }


@pytest.fixture
def config_file(tmp_path: Path, sample_config: dict) -> Path:
    path = tmp_path / "config.yaml"
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(sample_config, handle, allow_unicode=True, sort_keys=False)
    return path


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()


def test_load_editable_config_reads_config(config_file: Path, sample_config: dict):
    loaded = load_editable_config(config_path=config_file)
    assert loaded["portfolio"]["total_plan_amount"] == sample_config["portfolio"]["total_plan_amount"]
    assert len(loaded["assets"]) == 2


def test_validate_total_plan_amount_must_be_positive(sample_config: dict):
    sample_config["portfolio"]["total_plan_amount"] = 0
    errors = validate_editable_config(sample_config)
    assert any("计划总投入" in error for error in errors)


def test_validate_default_buy_amount_cannot_be_negative(sample_config: dict):
    sample_config["portfolio"]["default_buy_amount"] = -100
    errors = validate_editable_config(sample_config)
    assert any("默认买入金额" in error for error in errors)


def test_validate_target_weight_cannot_be_negative(sample_config: dict):
    sample_config["assets"][0]["target_weight"] = -0.1
    errors = validate_editable_config(sample_config)
    assert any("目标仓位" in error for error in errors)


def test_validate_max_weight_cannot_be_less_than_target(sample_config: dict):
    sample_config["assets"][0]["max_weight"] = 0.40
    sample_config["assets"][0]["target_weight"] = 0.50
    errors = validate_editable_config(sample_config)
    assert any("最大仓位" in error for error in errors)


def test_validate_target_weight_sum_cannot_exceed_100_percent(sample_config: dict):
    sample_config["assets"][0]["target_weight"] = 1.10
    errors = validate_editable_config(sample_config)
    assert any("100%" in error for error in errors)


def test_save_editable_config_creates_backup(config_file: Path, sample_config: dict, tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: tmp_path / "backups")

    updated = copy.deepcopy(sample_config)
    updated["portfolio"]["total_plan_amount"] = 120000

    backup_path = save_editable_config(updated, config_path=config_file)

    assert Path(backup_path).exists()
    saved = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert saved["portfolio"]["total_plan_amount"] == 120000


def test_save_does_not_overwrite_when_validation_fails(config_file: Path, sample_config: dict, monkeypatch):
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: Path("/tmp/unused"))

    original_text = config_file.read_text(encoding="utf-8")
    invalid = copy.deepcopy(sample_config)
    invalid["portfolio"]["total_plan_amount"] = -1

    with pytest.raises(ConfigValidationError):
        save_editable_config(invalid, config_path=config_file)

    assert config_file.read_text(encoding="utf-8") == original_text


def test_api_key_not_in_ai_settings_display(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret-should-not-leak")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")

    display = format_ai_settings_display()
    serialized = str(display)

    assert "api_key" not in display
    assert "secret-should-not-leak" not in serialized
    assert display["api_key_status"] == "已配置"


def test_config_editor_does_not_write_trade_log(config_file: Path, sample_config: dict, memory_conn, tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: tmp_path / "backups")
    upsert_etf_universe(memory_conn, sample_config["assets"])
    memory_conn.execute(
        """
        INSERT INTO trade_log (
            trade_date, symbol, action, amount, price, quantity, reason, emotion, is_rule_based
        ) VALUES ('2026-05-23', 'A500', 'buy', 1000, 1.0, 1000, 'test', 'calm', 1)
        """
    )
    memory_conn.commit()
    before = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]

    updated = copy.deepcopy(sample_config)
    updated["portfolio"]["total_plan_amount"] = 110000
    save_editable_config(updated, config_path=config_file)

    after = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    assert after == before


def test_config_editor_does_not_modify_holding_or_account_snapshot(
    config_file: Path,
    sample_config: dict,
    memory_conn,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: tmp_path / "backups")
    memory_conn.execute(
        """
        INSERT INTO account_snapshot (
            snapshot_date, cash_value, etf_market_value, total_account_value,
            total_position, cash_position
        ) VALUES ('2026-05-23', 20000, 80000, 100000, 0.8, 0.2)
        """
    )
    memory_conn.execute(
        """
        INSERT INTO holding_snapshot (
            snapshot_date, symbol, quantity, market_value, cost, weight
        ) VALUES ('2026-05-23', 'A500', 1000, 10000, 9000, 0.1)
        """
    )
    memory_conn.commit()
    account_before = memory_conn.execute(
        "SELECT total_account_value FROM account_snapshot"
    ).fetchone()[0]
    holding_before = memory_conn.execute("SELECT market_value FROM holding_snapshot").fetchone()[0]

    updated = copy.deepcopy(sample_config)
    updated["assets"][0]["target_weight"] = 0.45
    save_editable_config(updated, config_path=config_file)

    account_after = memory_conn.execute(
        "SELECT total_account_value FROM account_snapshot"
    ).fetchone()[0]
    holding_after = memory_conn.execute("SELECT market_value FROM holding_snapshot").fetchone()[0]
    assert account_after == account_before
    assert holding_after == holding_before


def test_config_editor_does_not_modify_strategy_signal(
    config_file: Path,
    sample_config: dict,
    memory_conn,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: tmp_path / "backups")
    upsert_etf_universe(memory_conn, sample_config["assets"])
    upsert_strategy_signals(
        memory_conn,
        [
            {
                "signal_date": "2026-05-23",
                "symbol": "A500",
                "final_score": 80,
                "trend_score": 20,
                "drawdown_score": 20,
                "anti_chase_score": 20,
                "position_score": 10,
                "special_score": 10,
                "volatility_score": 0,
                "action": "strong_buy",
                "suggested_amount": 3000,
                "reason": "test",
                "confidence_level": "normal",
                "review_status": "generated",
            }
        ],
    )
    memory_conn.commit()
    before = memory_conn.execute("SELECT final_score FROM strategy_signal").fetchone()[0]

    updated = copy.deepcopy(sample_config)
    updated["actions"]["strong_buy"]["min_score"] = 75
    save_editable_config(updated, config_path=config_file)

    after = memory_conn.execute("SELECT final_score FROM strategy_signal").fetchone()[0]
    assert after == before


def test_backup_config_file_creates_timestamped_copy(config_file: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: tmp_path / "backups")

    backup_path = backup_config_file(config_path=config_file)

    assert Path(backup_path).exists()
    assert "config_" in Path(backup_path).name
    assert yaml.safe_load(Path(backup_path).read_text(encoding="utf-8")) == yaml.safe_load(
        config_file.read_text(encoding="utf-8")
    )


def test_project_config_is_loadable():
    settings = load_settings()
    assert settings.get("portfolio")
    assert validate_editable_config(settings) == []
