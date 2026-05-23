from __future__ import annotations

import sqlite3

import pytest

from src.assets.queries import list_all_assets
from src.assets.validator import validate_asset_pool
from src.config.editor import load_editable_config, save_editable_config
from src.db.repository import create_or_update_etf_asset, disable_etf_asset, list_etf_universe
from src.db.schema import init_schema


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()


def test_settings_asset_flow_create_update_disable(memory_conn):
    create_or_update_etf_asset(
        memory_conn,
        {
            "symbol": "FLOW",
            "name": "流程测试",
            "fund_code": "510300",
            "exchange": "SH",
            "role": "satellite",
            "enabled": True,
            "enabled_for_signal": True,
            "target_weight": 0.10,
            "max_weight": 0.15,
        },
    )
    memory_conn.commit()

    assets = list_all_assets(memory_conn)
    errors = validate_asset_pool(assets)
    assert errors == []

    update_payload = {
        "symbol": "FLOW",
        "name": "流程测试更新",
        "fund_code": "510300",
        "exchange": "SH",
        "role": "satellite",
        "enabled": True,
        "enabled_for_signal": True,
        "target_weight": 0.12,
        "max_weight": 0.18,
    }
    from src.db.repository import update_etf_asset

    update_etf_asset(memory_conn, "FLOW", update_payload)
    memory_conn.commit()

    row = memory_conn.execute("SELECT name, target_weight FROM etf_universe WHERE symbol='FLOW'").fetchone()
    assert row["name"] == "流程测试更新"
    assert float(row["target_weight"]) == 0.12

    disable_etf_asset(memory_conn, "FLOW")
    memory_conn.commit()
    disabled = memory_conn.execute("SELECT enabled FROM etf_universe WHERE symbol='FLOW'").fetchone()
    assert disabled["enabled"] == 0
    assert len(list_etf_universe(memory_conn, enabled_only=False)) == 1


def test_save_editable_config_leaves_etf_universe_unchanged(tmp_path, memory_conn, monkeypatch):
    import yaml

    monkeypatch.setattr("src.config.editor.get_backup_dir", lambda: tmp_path / "backups")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.dump(
            {"portfolio": {"total_plan_amount": 100000}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    upsert = __import__("src.db.repository", fromlist=["upsert_etf_universe"]).upsert_etf_universe
    upsert(
        memory_conn,
        [{"symbol": "A500", "name": "数据库名称", "enabled": True, "target_weight": 0.4, "max_weight": 0.5}],
    )
    memory_conn.commit()

    draft = load_editable_config(config_path=config_path)
    draft["portfolio"]["total_plan_amount"] = 120000
    save_editable_config(draft, config_path=config_path)

    row = memory_conn.execute("SELECT name, target_weight FROM etf_universe WHERE symbol='A500'").fetchone()
    assert row["name"] == "数据库名称"
    assert float(row["target_weight"]) == 0.4

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "assets" not in saved
