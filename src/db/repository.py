from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd


def upsert_etf_universe(conn: sqlite3.Connection, assets: list[dict[str, Any]]) -> int:
    sql = """
    INSERT INTO etf_universe (
        symbol, name, fund_code, exchange, index_code, role, market,
        risk_level, target_weight, max_weight, min_weight, single_buy_ratio,
        enabled, enabled_for_signal, updated_at
    ) VALUES (
        :symbol, :name, :fund_code, :exchange, :index_code, :role, :market,
        :risk_level, :target_weight, :max_weight, :min_weight, :single_buy_ratio,
        :enabled, :enabled_for_signal, CURRENT_TIMESTAMP
    )
    ON CONFLICT(symbol) DO UPDATE SET
        name = excluded.name,
        fund_code = excluded.fund_code,
        exchange = excluded.exchange,
        index_code = excluded.index_code,
        role = excluded.role,
        market = excluded.market,
        risk_level = excluded.risk_level,
        target_weight = excluded.target_weight,
        max_weight = excluded.max_weight,
        min_weight = excluded.min_weight,
        single_buy_ratio = excluded.single_buy_ratio,
        enabled = excluded.enabled,
        enabled_for_signal = excluded.enabled_for_signal,
        updated_at = CURRENT_TIMESTAMP
    """
    count = 0
    for asset in assets:
        params = {
            "symbol": asset["symbol"],
            "name": asset["name"],
            "fund_code": asset.get("fund_code") or None,
            "exchange": asset.get("exchange") or None,
            "index_code": asset.get("index_code") or None,
            "role": asset.get("role"),
            "market": asset.get("market"),
            "risk_level": asset.get("risk_level", 3),
            "target_weight": asset.get("target_weight", 0),
            "max_weight": asset.get("max_weight", 0),
            "min_weight": asset.get("min_weight", 0),
            "single_buy_ratio": asset.get("single_buy_ratio", 0),
            "enabled": 1 if asset.get("enabled", True) else 0,
            "enabled_for_signal": 1 if asset.get("enabled_for_signal", True) else 0,
        }
        conn.execute(sql, params)
        count += 1
    return count


def list_etf_universe(conn: sqlite3.Connection, enabled_only: bool = False) -> list[sqlite3.Row]:
    if enabled_only:
        cur = conn.execute(
            "SELECT * FROM etf_universe WHERE enabled = 1 ORDER BY symbol"
        )
    else:
        cur = conn.execute("SELECT * FROM etf_universe ORDER BY symbol")
    return cur.fetchall()


def list_priceable_etfs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM etf_universe
        WHERE enabled = 1 AND fund_code IS NOT NULL AND fund_code != ''
        ORDER BY symbol
        """
    )
    return cur.fetchall()


def upsert_daily_prices(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    sql = """
    INSERT INTO daily_price (
        symbol, trade_date, open, high, low, close, volume, amount
    ) VALUES (
        :symbol, :trade_date, :open, :high, :low, :close, :volume, :amount
    )
    ON CONFLICT(symbol, trade_date) DO UPDATE SET
        open = excluded.open,
        high = excluded.high,
        low = excluded.low,
        close = excluded.close,
        volume = excluded.volume,
        amount = excluded.amount
    """
    records = df.to_dict("records")
    conn.executemany(sql, records)
    return len(records)


def get_daily_prices(conn: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    cur = conn.execute(
        """
        SELECT trade_date, open, high, low, close, volume, amount
        FROM daily_price
        WHERE symbol = ?
        ORDER BY trade_date
        """,
        (symbol,),
    )
    rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(
            columns=["trade_date", "open", "high", "low", "close", "volume", "amount"]
        )
    df = pd.DataFrame([dict(row) for row in rows])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def get_latest_daily_prices(conn: sqlite3.Connection, enabled_only: bool = False) -> pd.DataFrame:
    enabled_join = "INNER JOIN etf_universe eu ON dp.symbol = eu.symbol AND eu.enabled = 1"
    cur = conn.execute(
        f"""
        SELECT dp.*
        FROM daily_price dp
        {enabled_join if enabled_only else ""}
        INNER JOIN (
            SELECT symbol, MAX(trade_date) AS max_date
            FROM daily_price
            GROUP BY symbol
        ) latest
        ON dp.symbol = latest.symbol AND dp.trade_date = latest.max_date
        ORDER BY dp.symbol
        """
    )
    rows = cur.fetchall()
    return pd.DataFrame([dict(row) for row in rows]) if rows else pd.DataFrame()


def upsert_indicator_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
    INSERT INTO indicator_daily (
        symbol, trade_date, ma20, ma60, ma120, ma250,
        drawdown_60d, drawdown_120d, drawdown_250d,
        drawdown_used, drawdown_window,
        volatility_20d, return_5d, return_10d, return_20d,
        confidence_level
    ) VALUES (
        :symbol, :trade_date, :ma20, :ma60, :ma120, :ma250,
        :drawdown_60d, :drawdown_120d, :drawdown_250d,
        :drawdown_used, :drawdown_window,
        :volatility_20d, :return_5d, :return_10d, :return_20d,
        :confidence_level
    )
    ON CONFLICT(symbol, trade_date) DO UPDATE SET
        ma20 = excluded.ma20,
        ma60 = excluded.ma60,
        ma120 = excluded.ma120,
        ma250 = excluded.ma250,
        drawdown_60d = excluded.drawdown_60d,
        drawdown_120d = excluded.drawdown_120d,
        drawdown_250d = excluded.drawdown_250d,
        drawdown_used = excluded.drawdown_used,
        drawdown_window = excluded.drawdown_window,
        volatility_20d = excluded.volatility_20d,
        return_5d = excluded.return_5d,
        return_10d = excluded.return_10d,
        return_20d = excluded.return_20d,
        confidence_level = excluded.confidence_level
    """
    conn.executemany(sql, rows)
    return len(rows)


def get_latest_indicators(conn: sqlite3.Connection, enabled_only: bool = False) -> pd.DataFrame:
    enabled_join = "INNER JOIN etf_universe eu ON ind.symbol = eu.symbol AND eu.enabled = 1"
    cur = conn.execute(
        f"""
        SELECT ind.*
        FROM indicator_daily ind
        {enabled_join if enabled_only else ""}
        INNER JOIN (
            SELECT symbol, MAX(trade_date) AS max_date
            FROM indicator_daily
            GROUP BY symbol
        ) latest
        ON ind.symbol = latest.symbol AND ind.trade_date = latest.max_date
        ORDER BY ind.symbol
        """
    )
    rows = cur.fetchall()
    return pd.DataFrame([dict(row) for row in rows]) if rows else pd.DataFrame()


def save_account_snapshot(conn: sqlite3.Connection, snapshot: dict[str, Any]) -> None:
    sql = """
    INSERT INTO account_snapshot (
        snapshot_date, cash_value, etf_market_value, total_account_value,
        total_position, cash_position, note, updated_at
    ) VALUES (
        :snapshot_date, :cash_value, :etf_market_value, :total_account_value,
        :total_position, :cash_position, :note, CURRENT_TIMESTAMP
    )
    ON CONFLICT(snapshot_date) DO UPDATE SET
        cash_value = excluded.cash_value,
        etf_market_value = excluded.etf_market_value,
        total_account_value = excluded.total_account_value,
        total_position = excluded.total_position,
        cash_position = excluded.cash_position,
        note = excluded.note,
        updated_at = CURRENT_TIMESTAMP
    """
    params = {
        "snapshot_date": snapshot["snapshot_date"],
        "cash_value": snapshot.get("cash_value", 0),
        "etf_market_value": snapshot.get("etf_market_value", 0),
        "total_account_value": snapshot.get("total_account_value", 0),
        "total_position": snapshot.get("total_position", 0),
        "cash_position": snapshot.get("cash_position", 0),
        "note": snapshot.get("note"),
    }
    conn.execute(sql, params)


def get_latest_account_snapshot(conn: sqlite3.Connection) -> sqlite3.Row | None:
    cur = conn.execute(
        """
        SELECT * FROM account_snapshot
        ORDER BY snapshot_date DESC
        LIMIT 1
        """
    )
    return cur.fetchone()


def get_account_snapshot(conn: sqlite3.Connection, snapshot_date: str) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT * FROM account_snapshot WHERE snapshot_date = ?",
        (snapshot_date,),
    )
    return cur.fetchone()


def save_holding_snapshots(
    conn: sqlite3.Connection,
    snapshot_date: str,
    rows: list[dict[str, Any]],
) -> int:
    if not rows:
        conn.execute("DELETE FROM holding_snapshot WHERE snapshot_date = ?", (snapshot_date,))
        return 0

    sql = """
    INSERT INTO holding_snapshot (
        snapshot_date, symbol, quantity, market_value, cost,
        profit_loss, profit_loss_rate, weight
    ) VALUES (
        :snapshot_date, :symbol, :quantity, :market_value, :cost,
        :profit_loss, :profit_loss_rate, :weight
    )
    ON CONFLICT(snapshot_date, symbol) DO UPDATE SET
        quantity = excluded.quantity,
        market_value = excluded.market_value,
        cost = excluded.cost,
        profit_loss = excluded.profit_loss,
        profit_loss_rate = excluded.profit_loss_rate,
        weight = excluded.weight
    """
    records = []
    symbols = []
    for row in rows:
        if row.get("symbol") == "CASH":
            continue
        records.append(
            {
                "snapshot_date": snapshot_date,
                "symbol": row["symbol"],
                "quantity": row.get("quantity", 0),
                "market_value": row.get("market_value", 0),
                "cost": row.get("cost", 0),
                "profit_loss": row.get("profit_loss", 0),
                "profit_loss_rate": row.get("profit_loss_rate"),
                "weight": row.get("weight", 0),
            }
        )
        symbols.append(row["symbol"])

    conn.executemany(sql, records)
    if symbols:
        placeholders = ",".join("?" for _ in symbols)
        conn.execute(
            f"""
            DELETE FROM holding_snapshot
            WHERE snapshot_date = ? AND symbol NOT IN ({placeholders})
            """,
            [snapshot_date, *symbols],
        )
    else:
        conn.execute("DELETE FROM holding_snapshot WHERE snapshot_date = ?", (snapshot_date,))
    return len(records)


def get_holding_snapshots(
    conn: sqlite3.Connection,
    snapshot_date: str | None = None,
) -> list[sqlite3.Row]:
    if snapshot_date is None:
        latest = get_latest_account_snapshot(conn)
        if latest is None:
            return []
        snapshot_date = latest["snapshot_date"]

    cur = conn.execute(
        """
        SELECT * FROM holding_snapshot
        WHERE snapshot_date = ?
        ORDER BY symbol
        """,
        (snapshot_date,),
    )
    return cur.fetchall()


def get_latest_holding_snapshots(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return get_holding_snapshots(conn, snapshot_date=None)


def get_latest_price_map(conn: sqlite3.Connection) -> dict[str, float]:
    prices_df = get_latest_daily_prices(conn)
    if prices_df.empty:
        return {}
    price_map: dict[str, float] = {}
    for _, row in prices_df.iterrows():
        close = row.get("close")
        if pd.notna(close):
            price_map[str(row["symbol"])] = float(close)
    return price_map


def get_portfolio_overview(conn: sqlite3.Connection, settings: dict[str, Any]) -> dict[str, Any]:
    from src.portfolio.rebalance import build_alerts, build_position_rows

    account_row = get_latest_account_snapshot(conn)
    total_plan_amount = float(settings.get("portfolio", {}).get("total_plan_amount", 0))

    enabled_assets = [
        row for row in list_etf_universe(conn, enabled_only=True) if row["symbol"] != "CASH"
    ]
    universe_map = {
        row["symbol"]: {
            "name": row["name"],
            "target_weight": row["target_weight"],
            "max_weight": row["max_weight"],
            "enabled_for_signal": bool(row["enabled_for_signal"]),
        }
        for row in enabled_assets
    }

    if account_row is None:
        return {
            "snapshot_date": None,
            "total_plan_amount": total_plan_amount,
            "account": {
                "cash_value": 0.0,
                "etf_market_value": 0.0,
                "current_account_value": 0.0,
                "total_position": 0.0,
                "cash_position": 0.0,
                "valid": False,
            },
            "positions": [],
            "alerts": [],
        }

    snapshot_date = account_row["snapshot_date"]
    holdings = get_holding_snapshots(conn, snapshot_date)
    price_map = get_latest_price_map(conn)

    holding_dicts = []
    for row in holdings:
        item = dict(row)
        item["latest_price"] = price_map.get(item["symbol"])
        holding_dicts.append(item)

    account = {
        "cash_value": float(account_row["cash_value"] or 0),
        "etf_market_value": float(account_row["etf_market_value"] or 0),
        "current_account_value": float(account_row["total_account_value"] or 0),
        "total_position": float(account_row["total_position"] or 0),
        "cash_position": float(account_row["cash_position"] or 0),
        "valid": float(account_row["total_account_value"] or 0) > 0,
    }

    position_rows = build_position_rows(
        holding_dicts,
        universe_map,
        total_plan_amount,
        account,
    )

    return {
        "snapshot_date": snapshot_date,
        "total_plan_amount": total_plan_amount,
        "account": account,
        "positions": [row.__dict__ for row in position_rows],
        "alerts": [alert.__dict__ for alert in build_alerts(position_rows)],
    }


def upsert_strategy_signals(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
    INSERT INTO strategy_signal (
        signal_date, symbol, trend_score, drawdown_score, volatility_score,
        position_score, anti_chase_score, special_score, final_score, action,
        suggested_amount, reason, confidence_level, review_status
    ) VALUES (
        :signal_date, :symbol, :trend_score, :drawdown_score, :volatility_score,
        :position_score, :anti_chase_score, :special_score, :final_score, :action,
        :suggested_amount, :reason, :confidence_level, :review_status
    )
    ON CONFLICT(signal_date, symbol) DO UPDATE SET
        trend_score = excluded.trend_score,
        drawdown_score = excluded.drawdown_score,
        volatility_score = excluded.volatility_score,
        position_score = excluded.position_score,
        anti_chase_score = excluded.anti_chase_score,
        special_score = excluded.special_score,
        final_score = excluded.final_score,
        action = excluded.action,
        suggested_amount = excluded.suggested_amount,
        reason = excluded.reason,
        confidence_level = excluded.confidence_level,
        review_status = excluded.review_status
    """
    conn.executemany(sql, rows)
    return len(rows)


def get_strategy_signals_by_date(conn: sqlite3.Connection, signal_date: str) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT ss.*, eu.name
        FROM strategy_signal ss
        LEFT JOIN etf_universe eu ON ss.symbol = eu.symbol
        WHERE ss.signal_date = ?
        ORDER BY ss.symbol
        """,
        (signal_date,),
    )
    return cur.fetchall()


def get_latest_strategy_signal_date(conn: sqlite3.Connection) -> str | None:
    cur = conn.execute("SELECT MAX(signal_date) AS max_date FROM strategy_signal")
    row = cur.fetchone()
    if row is None or row["max_date"] is None:
        return None
    return str(row["max_date"])


def get_latest_strategy_signals(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    signal_date = get_latest_strategy_signal_date(conn)
    if signal_date is None:
        return []
    return get_strategy_signals_by_date(conn, signal_date)


def update_strategy_signal_review_status(
    conn: sqlite3.Connection,
    signal_id: int,
    review_status: str,
) -> None:
    if review_status in {"reviewed", "executed"}:
        conn.execute(
            """
            UPDATE strategy_signal
            SET review_status = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (review_status, signal_id),
        )
        return
    conn.execute(
        """
        UPDATE strategy_signal
        SET review_status = ?, reviewed_at = NULL
        WHERE id = ?
        """,
        (review_status, signal_id),
    )


def save_trade_log(conn: sqlite3.Connection, row: dict[str, Any]) -> int:
    sql = """
    INSERT INTO trade_log (
        trade_date, symbol, signal_id, action, amount, price, quantity,
        reason, emotion, is_rule_based, suggested_amount, deviation_amount,
        execution_status, note
    ) VALUES (
        :trade_date, :symbol, :signal_id, :action, :amount, :price, :quantity,
        :reason, :emotion, :is_rule_based, :suggested_amount, :deviation_amount,
        :execution_status, :note
    )
    """
    cur = conn.execute(sql, row)
    return int(cur.lastrowid)


def get_trade_logs(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
    symbol: str | None = None,
) -> list[sqlite3.Row]:
    sql = """
    SELECT tl.*, eu.name
    FROM trade_log tl
    LEFT JOIN etf_universe eu ON tl.symbol = eu.symbol
    WHERE 1=1
    """
    params: list[Any] = []
    if start_date:
        sql += " AND tl.trade_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND tl.trade_date <= ?"
        params.append(end_date)
    if symbol:
        sql += " AND tl.symbol = ?"
        params.append(symbol)
    sql += " ORDER BY tl.trade_date DESC, tl.id DESC"
    cur = conn.execute(sql, params)
    return cur.fetchall()


def get_trade_log_by_id(conn: sqlite3.Connection, trade_id: int) -> sqlite3.Row | None:
    cur = conn.execute(
        """
        SELECT tl.*, eu.name
        FROM trade_log tl
        LEFT JOIN etf_universe eu ON tl.symbol = eu.symbol
        WHERE tl.id = ?
        """,
        (trade_id,),
    )
    return cur.fetchone()


def get_trade_logs_by_signal_id(conn: sqlite3.Connection, signal_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT tl.*, eu.name
        FROM trade_log tl
        LEFT JOIN etf_universe eu ON tl.symbol = eu.symbol
        WHERE tl.signal_id = ?
        ORDER BY tl.trade_date DESC, tl.id DESC
        """,
        (signal_id,),
    )
    return cur.fetchall()


def get_recent_trade_logs(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT tl.*, eu.name
        FROM trade_log tl
        LEFT JOIN etf_universe eu ON tl.symbol = eu.symbol
        ORDER BY tl.trade_date DESC, tl.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cur.fetchall()


def upsert_daily_report(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    sql = """
    INSERT INTO daily_report (
        report_date, total_position, cash_position,
        summary, risk_warning, action_suggestion
    ) VALUES (
        :report_date, :total_position, :cash_position,
        :summary, :risk_warning, :action_suggestion
    )
    ON CONFLICT(report_date) DO UPDATE SET
        total_position = excluded.total_position,
        cash_position = excluded.cash_position,
        summary = excluded.summary,
        risk_warning = excluded.risk_warning,
        action_suggestion = excluded.action_suggestion
    """
    conn.execute(sql, row)


def get_daily_report_by_date(conn: sqlite3.Connection, report_date: str) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT * FROM daily_report WHERE report_date = ?",
        (report_date,),
    )
    return cur.fetchone()


def get_latest_daily_report(conn: sqlite3.Connection) -> sqlite3.Row | None:
    cur = conn.execute(
        """
        SELECT * FROM daily_report
        ORDER BY report_date DESC
        LIMIT 1
        """
    )
    return cur.fetchone()


def list_daily_reports(conn: sqlite3.Connection, limit: int = 30) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM daily_report
        ORDER BY report_date DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cur.fetchall()


def upsert_weekly_report(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    sql = """
    INSERT INTO weekly_report (
        week_start, week_end, summary, discipline_summary,
        risk_summary, action_suggestion
    ) VALUES (
        :week_start, :week_end, :summary, :discipline_summary,
        :risk_summary, :action_suggestion
    )
    ON CONFLICT(week_start, week_end) DO UPDATE SET
        summary = excluded.summary,
        discipline_summary = excluded.discipline_summary,
        risk_summary = excluded.risk_summary,
        action_suggestion = excluded.action_suggestion
    """
    conn.execute(sql, row)


def get_weekly_report(
    conn: sqlite3.Connection,
    week_start: str,
    week_end: str,
) -> sqlite3.Row | None:
    cur = conn.execute(
        """
        SELECT * FROM weekly_report
        WHERE week_start = ? AND week_end = ?
        """,
        (week_start, week_end),
    )
    return cur.fetchone()


def get_latest_weekly_report(conn: sqlite3.Connection) -> sqlite3.Row | None:
    cur = conn.execute(
        """
        SELECT * FROM weekly_report
        ORDER BY week_end DESC, week_start DESC
        LIMIT 1
        """
    )
    return cur.fetchone()


def list_weekly_reports(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM weekly_report
        ORDER BY week_end DESC, week_start DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cur.fetchall()


def upsert_ai_review(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    sql = """
    INSERT INTO ai_review (
        review_type, target_date, week_start, week_end, source_type, source_digest,
        prompt_version, provider, model, input_snapshot, output_text,
        discipline_summary, behavior_findings, risk_summary, action_suggestion, status, error_message
    ) VALUES (
        :review_type, :target_date, :week_start, :week_end, :source_type, :source_digest,
        :prompt_version, :provider, :model, :input_snapshot, :output_text,
        :discipline_summary, :behavior_findings, :risk_summary, :action_suggestion, :status, :error_message
    )
    ON CONFLICT(review_type, target_date, week_start, week_end, prompt_version) DO UPDATE SET
        source_type = excluded.source_type,
        source_digest = excluded.source_digest,
        provider = excluded.provider,
        model = excluded.model,
        input_snapshot = excluded.input_snapshot,
        output_text = excluded.output_text,
        discipline_summary = excluded.discipline_summary,
        behavior_findings = excluded.behavior_findings,
        risk_summary = excluded.risk_summary,
        action_suggestion = excluded.action_suggestion,
        status = excluded.status,
        error_message = excluded.error_message
    """
    conn.execute(sql, row)


def get_ai_review_by_daily_date(
    conn: sqlite3.Connection,
    target_date: str,
    prompt_version: str = "v1",
) -> sqlite3.Row | None:
    cur = conn.execute(
        """
        SELECT * FROM ai_review
        WHERE review_type = 'daily' AND target_date = ? AND prompt_version = ?
        """,
        (target_date, prompt_version),
    )
    return cur.fetchone()


def get_ai_review_by_week(
    conn: sqlite3.Connection,
    week_start: str,
    week_end: str,
    prompt_version: str = "v1",
) -> sqlite3.Row | None:
    cur = conn.execute(
        """
        SELECT * FROM ai_review
        WHERE review_type = 'weekly'
          AND week_start = ? AND week_end = ? AND prompt_version = ?
        """,
        (week_start, week_end, prompt_version),
    )
    return cur.fetchone()


def get_latest_ai_reviews(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM ai_review
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cur.fetchall()


def list_ai_reviews(
    conn: sqlite3.Connection,
    review_type: str | None = None,
    limit: int = 30,
) -> list[sqlite3.Row]:
    if review_type:
        cur = conn.execute(
            """
            SELECT * FROM ai_review
            WHERE review_type = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (review_type, limit),
        )
    else:
        cur = conn.execute(
            """
            SELECT * FROM ai_review
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
    return cur.fetchall()


def save_backtest_run(conn: sqlite3.Connection, row: dict[str, Any]) -> int:
    cur = conn.execute(
        """
        INSERT INTO backtest_run (
            run_name, symbol, strategy_name, start_date, end_date,
            initial_cash, fixed_amount, frequency, params_json
        ) VALUES (
            :run_name, :symbol, :strategy_name, :start_date, :end_date,
            :initial_cash, :fixed_amount, :frequency, :params_json
        )
        """,
        row,
    )
    return int(cur.lastrowid)


def save_backtest_result(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO backtest_result (
            run_id, final_value, total_invested, cash_value, position_value,
            total_return, annualized_return, max_drawdown, trade_count,
            final_quantity, average_cost, actual_start_date, actual_end_date, trading_days
        ) VALUES (
            :run_id, :final_value, :total_invested, :cash_value, :position_value,
            :total_return, :annualized_return, :max_drawdown, :trade_count,
            :final_quantity, :average_cost, :actual_start_date, :actual_end_date, :trading_days
        )
        """,
        row,
    )


def save_backtest_trades(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO backtest_trade (
            run_id, trade_date, symbol, action, price, amount, quantity, reason
        ) VALUES (
            :run_id, :trade_date, :symbol, :action, :price, :amount, :quantity, :reason
        )
        """,
        rows,
    )


def save_backtest_equity_curve(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO backtest_equity_curve (
            run_id, trade_date, cash_value, position_value, total_value, drawdown
        ) VALUES (
            :run_id, :trade_date, :cash_value, :position_value, :total_value, :drawdown
        )
        """,
        rows,
    )


def get_backtest_run(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM backtest_run WHERE id = ?", (run_id,))
    return cur.fetchone()


def get_backtest_result(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM backtest_result WHERE run_id = ?", (run_id,))
    return cur.fetchone()


def get_backtest_trades(conn: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM backtest_trade
        WHERE run_id = ?
        ORDER BY trade_date
        """,
        (run_id,),
    )
    return cur.fetchall()


def get_backtest_equity_curve(conn: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM backtest_equity_curve
        WHERE run_id = ?
        ORDER BY trade_date
        """,
        (run_id,),
    )
    return cur.fetchall()


def list_backtest_runs(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM backtest_run
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cur.fetchall()
