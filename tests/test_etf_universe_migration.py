from __future__ import annotations

import sqlite3

from src.db.schema import _table_has_column, apply_schema_migrations, init_schema

LEGACY_ETF_UNIVERSE_DDL = """
CREATE TABLE etf_universe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    fund_code TEXT,
    exchange TEXT,
    index_code TEXT,
    role TEXT,
    market TEXT,
    risk_level INTEGER DEFAULT 3,
    target_weight REAL DEFAULT 0,
    max_weight REAL DEFAULT 0,
    min_weight REAL DEFAULT 0,
    single_buy_ratio REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


def _create_legacy_etf_universe(conn: sqlite3.Connection) -> None:
    conn.execute(LEGACY_ETF_UNIVERSE_DDL)
    conn.execute(
        """
        INSERT INTO etf_universe (
            symbol, name, fund_code, exchange, role, target_weight, max_weight
        ) VALUES ('A500', '中证A500ETF', '512050', 'SH', 'core', 0.5, 0.65)
        """
    )
    conn.commit()


def test_apply_schema_migrations_adds_enabled_columns_to_legacy_etf_universe():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_legacy_etf_universe(conn)

    assert not _table_has_column(conn, "etf_universe", "enabled")
    assert not _table_has_column(conn, "etf_universe", "enabled_for_signal")

    apply_schema_migrations(conn)

    assert _table_has_column(conn, "etf_universe", "enabled")
    assert _table_has_column(conn, "etf_universe", "enabled_for_signal")


def test_init_schema_migrates_legacy_etf_universe_without_dropping_rows():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_legacy_etf_universe(conn)

    init_schema(conn)

    assert _table_has_column(conn, "etf_universe", "enabled")
    assert _table_has_column(conn, "etf_universe", "enabled_for_signal")

    row = conn.execute(
        "SELECT symbol, name, enabled, enabled_for_signal FROM etf_universe WHERE symbol = 'A500'"
    ).fetchone()
    assert row is not None
    assert row["symbol"] == "A500"
    assert row["name"] == "中证A500ETF"
    assert row["enabled"] == 1
    assert row["enabled_for_signal"] == 1

    count = conn.execute("SELECT COUNT(*) FROM etf_universe").fetchone()[0]
    assert count == 1
