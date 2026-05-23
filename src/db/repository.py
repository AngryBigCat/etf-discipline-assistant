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
