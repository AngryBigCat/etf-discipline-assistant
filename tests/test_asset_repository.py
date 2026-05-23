from __future__ import annotations

import sqlite3

import pytest

from src.config.editor import format_ai_settings_display
from src.db.repository import (
    create_or_update_etf_asset,
    disable_etf_asset,
    get_etf_asset,
    list_priceable_etfs,
    list_signal_enabled_etfs,
    update_etf_asset,
    upsert_etf_universe,
    upsert_strategy_signals,
)
from src.db.schema import init_schema


@pytest.fixture
def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()


def _sample_asset(**overrides) -> dict:
    asset = {
        "symbol": "NEWETF",
        "name": "新标的",
        "fund_code": "159915",
        "exchange": "SZ",
        "role": "satellite",
        "enabled": True,
        "enabled_for_signal": False,
        "target_weight": 0.05,
        "max_weight": 0.10,
    }
    asset.update(overrides)
    return asset


def _seed_existing_universe(memory_conn) -> None:
    upsert_etf_universe(
        memory_conn,
        [
            {
                "symbol": "RETIRED",
                "name": "已停用旧标的",
                "fund_code": "510050",
                "exchange": "SH",
                "role": "satellite",
                "enabled": True,
                "enabled_for_signal": False,
                "target_weight": 0.05,
                "max_weight": 0.10,
            }
        ],
    )
    memory_conn.execute(
        """
        INSERT INTO daily_price (symbol, trade_date, close, open, high, low, volume, amount)
        VALUES ('RETIRED', '2026-05-23', 1.0, 1.0, 1.0, 1.0, 100, 100)
        """
    )
    memory_conn.execute(
        """
        INSERT INTO trade_log (trade_date, symbol, action, amount, price, quantity, reason, emotion, is_rule_based)
        VALUES ('2026-05-23', 'RETIRED', 'buy', 1000, 1.0, 1000, 'test', 'calm', 1)
        """
    )
    memory_conn.execute(
        """
        INSERT INTO holding_snapshot (
            snapshot_date, symbol, quantity, market_value, cost, weight
        ) VALUES ('2026-05-23', 'RETIRED', 1000, 10000, 9000, 0.1)
        """
    )
    upsert_strategy_signals(
        memory_conn,
        [
            {
                "signal_date": "2026-05-23",
                "symbol": "RETIRED",
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


def test_create_or_update_etf_asset_inserts_new_record(memory_conn):
    create_or_update_etf_asset(memory_conn, _sample_asset())
    memory_conn.commit()
    row = get_etf_asset(memory_conn, "NEWETF")
    assert row is not None
    assert row["name"] == "新标的"


def test_update_etf_asset_updates_existing_record(memory_conn):
    create_or_update_etf_asset(memory_conn, _sample_asset())
    update_etf_asset(memory_conn, "NEWETF", {"name": "更新名称", "target_weight": 0.08})
    memory_conn.commit()
    row = get_etf_asset(memory_conn, "NEWETF")
    assert row["name"] == "更新名称"
    assert float(row["target_weight"]) == 0.08


def test_disable_etf_asset_sets_enabled_zero(memory_conn):
    create_or_update_etf_asset(memory_conn, _sample_asset())
    disable_etf_asset(memory_conn, "NEWETF")
    memory_conn.commit()
    row = get_etf_asset(memory_conn, "NEWETF")
    assert row["enabled"] == 0


def test_disable_does_not_delete_daily_price(memory_conn):
    _seed_existing_universe(memory_conn)
    before = memory_conn.execute("SELECT COUNT(*) FROM daily_price").fetchone()[0]
    disable_etf_asset(memory_conn, "RETIRED")
    memory_conn.commit()
    after = memory_conn.execute("SELECT COUNT(*) FROM daily_price").fetchone()[0]
    assert after == before


def test_disable_does_not_delete_trade_log(memory_conn):
    _seed_existing_universe(memory_conn)
    before = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    disable_etf_asset(memory_conn, "RETIRED")
    memory_conn.commit()
    after = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    assert after == before


def test_disable_does_not_modify_holding_snapshot(memory_conn):
    _seed_existing_universe(memory_conn)
    before = memory_conn.execute(
        "SELECT market_value FROM holding_snapshot WHERE symbol='RETIRED'"
    ).fetchone()[0]
    disable_etf_asset(memory_conn, "RETIRED")
    memory_conn.commit()
    after = memory_conn.execute(
        "SELECT market_value FROM holding_snapshot WHERE symbol='RETIRED'"
    ).fetchone()[0]
    assert after == before


def test_disable_does_not_modify_strategy_signal(memory_conn):
    _seed_existing_universe(memory_conn)
    before = memory_conn.execute(
        "SELECT final_score FROM strategy_signal WHERE symbol='RETIRED'"
    ).fetchone()[0]
    disable_etf_asset(memory_conn, "RETIRED")
    memory_conn.commit()
    after = memory_conn.execute(
        "SELECT final_score FROM strategy_signal WHERE symbol='RETIRED'"
    ).fetchone()[0]
    assert after == before


def test_disabled_asset_not_in_list_priceable_etfs(memory_conn):
    create_or_update_etf_asset(memory_conn, _sample_asset(enabled=False))
    memory_conn.commit()
    symbols = [row["symbol"] for row in list_priceable_etfs(memory_conn)]
    assert "NEWETF" not in symbols


def test_enabled_asset_with_fund_code_in_list_priceable_etfs(memory_conn):
    create_or_update_etf_asset(memory_conn, _sample_asset())
    memory_conn.commit()
    symbols = [row["symbol"] for row in list_priceable_etfs(memory_conn)]
    assert "NEWETF" in symbols


def test_signal_disabled_asset_not_in_list_signal_enabled_etfs(memory_conn):
    create_or_update_etf_asset(memory_conn, _sample_asset(enabled_for_signal=False))
    memory_conn.commit()
    symbols = [row["symbol"] for row in list_signal_enabled_etfs(memory_conn)]
    assert "NEWETF" not in symbols


def test_signal_enabled_asset_in_list_signal_enabled_etfs(memory_conn):
    create_or_update_etf_asset(
        memory_conn,
        _sample_asset(enabled_for_signal=True, symbol="SIGETF"),
    )
    memory_conn.commit()
    symbols = [row["symbol"] for row in list_signal_enabled_etfs(memory_conn)]
    assert "SIGETF" in symbols


def test_upsert_does_not_delete_old_symbols(memory_conn):
    _seed_existing_universe(memory_conn)
    create_or_update_etf_asset(memory_conn, _sample_asset())
    memory_conn.commit()
    symbols = {row["symbol"] for row in memory_conn.execute("SELECT symbol FROM etf_universe").fetchall()}
    assert "RETIRED" in symbols


def test_api_key_not_in_ai_settings_display(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret-should-not-leak")
    display = format_ai_settings_display()
    assert "secret-should-not-leak" not in str(display)
