from __future__ import annotations

import sqlite3

SCHEMA_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS etf_universe (
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
        enabled INTEGER DEFAULT 1,
        enabled_for_signal INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_price (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        amount REAL,
        nav REAL,
        premium_rate REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, trade_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS account_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_date TEXT NOT NULL UNIQUE,
        cash_value REAL NOT NULL DEFAULT 0,
        etf_market_value REAL NOT NULL DEFAULT 0,
        total_account_value REAL NOT NULL DEFAULT 0,
        total_position REAL DEFAULT 0,
        cash_position REAL DEFAULT 0,
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS holding_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        quantity REAL DEFAULT 0,
        market_value REAL NOT NULL,
        cost REAL DEFAULT 0,
        profit_loss REAL DEFAULT 0,
        profit_loss_rate REAL DEFAULT 0,
        weight REAL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(snapshot_date, symbol)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trade_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        signal_id INTEGER,
        action TEXT NOT NULL,
        amount REAL NOT NULL,
        price REAL,
        quantity REAL,
        reason TEXT,
        emotion TEXT,
        is_rule_based INTEGER DEFAULT 1,
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (signal_id) REFERENCES strategy_signal(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS indicator_daily (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        ma20 REAL,
        ma60 REAL,
        ma120 REAL,
        ma250 REAL,
        drawdown_60d REAL,
        drawdown_120d REAL,
        drawdown_250d REAL,
        drawdown_used REAL,
        drawdown_window INTEGER,
        volatility_20d REAL,
        return_5d REAL,
        return_10d REAL,
        return_20d REAL,
        confidence_level TEXT DEFAULT 'normal',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, trade_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_signal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        trend_score REAL DEFAULT 0,
        drawdown_score REAL DEFAULT 0,
        volatility_score REAL DEFAULT 0,
        position_score REAL DEFAULT 0,
        anti_chase_score REAL DEFAULT 0,
        special_score REAL DEFAULT 0,
        final_score REAL DEFAULT 0,
        action TEXT,
        suggested_amount REAL DEFAULT 0,
        reason TEXT,
        confidence_level TEXT DEFAULT 'normal',
        review_status TEXT DEFAULT 'generated',
        reviewed_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(signal_date, symbol)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_report (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL UNIQUE,
        total_position REAL,
        cash_position REAL,
        summary TEXT,
        risk_warning TEXT,
        action_suggestion TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_daily_price_symbol_date ON daily_price(symbol, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_indicator_daily_symbol_date ON indicator_daily(symbol, trade_date)",
]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cur.fetchone() is not None


def _table_has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def apply_schema_migrations(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "strategy_signal"):
        return
    if not _table_has_column(conn, "strategy_signal", "special_score"):
        conn.execute(
            "ALTER TABLE strategy_signal ADD COLUMN special_score REAL DEFAULT 0"
        )


def init_schema(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    apply_schema_migrations(conn)
