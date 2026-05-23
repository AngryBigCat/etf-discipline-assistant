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
        suggested_amount REAL DEFAULT 0,
        deviation_amount REAL DEFAULT 0,
        execution_status TEXT DEFAULT 'recorded',
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
    """
    CREATE TABLE IF NOT EXISTS weekly_report (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start TEXT NOT NULL,
        week_end TEXT NOT NULL,
        summary TEXT,
        discipline_summary TEXT,
        risk_summary TEXT,
        action_suggestion TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(week_start, week_end)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_review (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        review_type TEXT NOT NULL,
        target_date TEXT NOT NULL DEFAULT '',
        week_start TEXT NOT NULL DEFAULT '',
        week_end TEXT NOT NULL DEFAULT '',
        source_type TEXT NOT NULL,
        source_digest TEXT,
        prompt_version TEXT NOT NULL DEFAULT 'v1',
        provider TEXT DEFAULT 'mock',
        model TEXT,
        input_snapshot TEXT,
        output_text TEXT,
        discipline_summary TEXT,
        behavior_findings TEXT,
        risk_summary TEXT,
        action_suggestion TEXT,
        status TEXT DEFAULT 'success',
        error_message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(review_type, target_date, week_start, week_end, prompt_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_run (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_name TEXT,
        symbol TEXT NOT NULL,
        strategy_name TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        initial_cash REAL NOT NULL,
        fixed_amount REAL NOT NULL,
        frequency TEXT NOT NULL,
        params_json TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_result (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        final_value REAL,
        total_invested REAL,
        cash_value REAL,
        position_value REAL,
        total_return REAL,
        annualized_return REAL,
        max_drawdown REAL,
        trade_count INTEGER,
        final_quantity REAL,
        average_cost REAL,
        actual_start_date TEXT,
        actual_end_date TEXT,
        trading_days INTEGER,
        cash_utilization REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(run_id) REFERENCES backtest_run(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_trade (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        trade_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        action TEXT NOT NULL,
        price REAL NOT NULL,
        amount REAL NOT NULL,
        quantity REAL NOT NULL,
        reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(run_id) REFERENCES backtest_run(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_equity_curve (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        trade_date TEXT NOT NULL,
        cash_value REAL,
        position_value REAL,
        total_value REAL,
        drawdown REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(run_id) REFERENCES backtest_run(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_position (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        quantity REAL,
        average_cost REAL,
        last_price REAL,
        market_value REAL,
        weight REAL,
        target_weight REAL,
        deviation REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(run_id) REFERENCES backtest_run(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_daily_price_symbol_date ON daily_price(symbol, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_indicator_daily_symbol_date ON indicator_daily(symbol, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_trade_log_trade_date ON trade_log(trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_backtest_run_created_at ON backtest_run(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_backtest_trade_run_id ON backtest_trade(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_backtest_equity_run_date ON backtest_equity_curve(run_id, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_backtest_position_run_id ON backtest_position(run_id)",
    """
    CREATE TABLE IF NOT EXISTS task_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_date TEXT NOT NULL,
        category TEXT NOT NULL,
        task_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        priority TEXT DEFAULT 'normal',
        status TEXT DEFAULT 'pending',
        source_type TEXT,
        source_key TEXT,
        due_date TEXT,
        completed_at TEXT,
        skipped_at TEXT,
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(task_date, task_type, source_type, source_key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_task_item_date_status ON task_item(task_date, status)",
    """
    CREATE TABLE IF NOT EXISTS task_action_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        task_date TEXT,
        task_type TEXT NOT NULL,
        action_name TEXT NOT NULL,
        success INTEGER NOT NULL,
        message TEXT,
        detail TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(task_id) REFERENCES task_item(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_task_action_log_task_id ON task_action_log(task_id)",
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
    if _table_exists(conn, "strategy_signal"):
        if not _table_has_column(conn, "strategy_signal", "special_score"):
            conn.execute(
                "ALTER TABLE strategy_signal ADD COLUMN special_score REAL DEFAULT 0"
            )

    if _table_exists(conn, "trade_log"):
        trade_log_columns = {
            "suggested_amount": "REAL DEFAULT 0",
            "deviation_amount": "REAL DEFAULT 0",
            "execution_status": "TEXT DEFAULT 'recorded'",
        }
        for column_name, column_def in trade_log_columns.items():
            if not _table_has_column(conn, "trade_log", column_name):
                conn.execute(
                    f"ALTER TABLE trade_log ADD COLUMN {column_name} {column_def}"
                )

    if _table_exists(conn, "ai_review") and not _table_has_column(
        conn, "ai_review", "behavior_findings"
    ):
        conn.execute("ALTER TABLE ai_review ADD COLUMN behavior_findings TEXT")

    if _table_exists(conn, "backtest_result"):
        backtest_result_columns = {
            "actual_start_date": "TEXT",
            "actual_end_date": "TEXT",
            "trading_days": "INTEGER",
            "cash_utilization": "REAL",
        }
        for column_name, column_def in backtest_result_columns.items():
            if not _table_has_column(conn, "backtest_result", column_name):
                conn.execute(
                    f"ALTER TABLE backtest_result ADD COLUMN {column_name} {column_def}"
                )


def init_schema(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    apply_schema_migrations(conn)
