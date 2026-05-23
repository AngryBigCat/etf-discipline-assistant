from __future__ import annotations

import pytest

from src.config.editor import format_ai_settings_display
from src.config.sync import sync_assets_to_etf_universe
from src.db.repository import list_etf_universe, upsert_etf_universe, upsert_strategy_signals
from src.db.schema import init_schema


@pytest.fixture
def sample_config() -> dict:
    return {
        "assets": [
            {
                "symbol": "A500",
                "name": "中证A500ETF",
                "fund_code": "512050",
                "exchange": "SH",
                "role": "core",
                "enabled": True,
                "enabled_for_signal": True,
                "target_weight": 0.50,
                "max_weight": 0.65,
            },
            {
                "symbol": "NEWETF",
                "name": "新标的",
                "fund_code": "159915",
                "exchange": "SZ",
                "role": "satellite",
                "enabled": True,
                "enabled_for_signal": False,
                "target_weight": 0.05,
                "max_weight": 0.10,
            },
        ]
    }


@pytest.fixture
def memory_conn():
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()


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


def test_sync_assets_to_etf_universe_inserts_new_assets(memory_conn, sample_config: dict):
    result = sync_assets_to_etf_universe(memory_conn, sample_config)
    memory_conn.commit()

    symbols = {row["symbol"] for row in list_etf_universe(memory_conn, enabled_only=False)}
    assert result["synced_count"] == 2
    assert "A500" in symbols
    assert "NEWETF" in symbols
    assert "NEWETF" in result["new_symbols"]


def test_sync_assets_to_etf_universe_does_not_delete_old_symbols(memory_conn, sample_config: dict):
    _seed_existing_universe(memory_conn)

    sync_assets_to_etf_universe(memory_conn, sample_config)
    memory_conn.commit()

    symbols = {row["symbol"] for row in list_etf_universe(memory_conn, enabled_only=False)}
    assert "RETIRED" in symbols


def test_sync_assets_to_etf_universe_persists_disabled_flag(memory_conn):
    config = {
        "assets": [
            {
                "symbol": "HIDDEN",
                "name": "隐藏标的",
                "fund_code": "510300",
                "exchange": "SH",
                "role": "satellite",
                "enabled": False,
                "enabled_for_signal": False,
                "target_weight": 0,
                "max_weight": 0,
            }
        ]
    }

    sync_assets_to_etf_universe(memory_conn, config)
    memory_conn.commit()

    row = memory_conn.execute(
        "SELECT enabled FROM etf_universe WHERE symbol = 'HIDDEN'"
    ).fetchone()
    assert row is not None
    assert row["enabled"] == 0


def test_sync_assets_to_etf_universe_does_not_delete_daily_price(memory_conn, sample_config: dict):
    _seed_existing_universe(memory_conn)
    before = memory_conn.execute("SELECT COUNT(*) FROM daily_price").fetchone()[0]

    sync_assets_to_etf_universe(memory_conn, sample_config)
    memory_conn.commit()

    after = memory_conn.execute("SELECT COUNT(*) FROM daily_price").fetchone()[0]
    assert after == before


def test_sync_assets_to_etf_universe_does_not_delete_trade_log(memory_conn, sample_config: dict):
    _seed_existing_universe(memory_conn)
    before = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]

    sync_assets_to_etf_universe(memory_conn, sample_config)
    memory_conn.commit()

    after = memory_conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    assert after == before


def test_sync_assets_to_etf_universe_does_not_modify_holding_snapshot(memory_conn, sample_config: dict):
    _seed_existing_universe(memory_conn)
    before = memory_conn.execute(
        "SELECT market_value FROM holding_snapshot WHERE symbol = 'RETIRED'"
    ).fetchone()[0]

    sync_assets_to_etf_universe(memory_conn, sample_config)
    memory_conn.commit()

    after = memory_conn.execute(
        "SELECT market_value FROM holding_snapshot WHERE symbol = 'RETIRED'"
    ).fetchone()[0]
    assert after == before


def test_sync_assets_to_etf_universe_does_not_modify_strategy_signal(memory_conn, sample_config: dict):
    _seed_existing_universe(memory_conn)
    before = memory_conn.execute(
        "SELECT final_score FROM strategy_signal WHERE symbol = 'RETIRED'"
    ).fetchone()[0]

    sync_assets_to_etf_universe(memory_conn, sample_config)
    memory_conn.commit()

    after = memory_conn.execute(
        "SELECT final_score FROM strategy_signal WHERE symbol = 'RETIRED'"
    ).fetchone()[0]
    assert after == before


def test_sync_assets_to_etf_universe_does_not_modify_account_snapshot(memory_conn, sample_config: dict):
    _seed_existing_universe(memory_conn)
    before = memory_conn.execute(
        "SELECT total_account_value FROM account_snapshot"
    ).fetchone()[0]

    sync_assets_to_etf_universe(memory_conn, sample_config)
    memory_conn.commit()

    after = memory_conn.execute(
        "SELECT total_account_value FROM account_snapshot"
    ).fetchone()[0]
    assert after == before


def test_api_key_not_in_ai_settings_display(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret-should-not-leak")
    display = format_ai_settings_display()
    assert "secret-should-not-leak" not in str(display)
