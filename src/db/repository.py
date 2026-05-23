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


def get_latest_daily_prices(conn: sqlite3.Connection) -> pd.DataFrame:
    cur = conn.execute(
        """
        SELECT dp.*
        FROM daily_price dp
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


def get_latest_indicators(conn: sqlite3.Connection) -> pd.DataFrame:
    cur = conn.execute(
        """
        SELECT ind.*
        FROM indicator_daily ind
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
        "alerts": build_alerts(position_rows),
    }
