from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from src.collectors.akshare_collector import AkshareCollector
from src.db.repository import get_etf_asset, list_priceable_etfs, upsert_daily_prices
from src.utils.network import build_network_hint, is_connection_error


@dataclass
class BackfillResult:
    symbol: str
    success: bool
    rows: int
    start_date: str
    end_date: str
    message: str


def _resolve_fund_code(conn, symbol: str) -> str:
    row = get_etf_asset(conn, symbol)
    if row is None:
        raise ValueError(f"未在标的池中找到：{symbol}")
    if not int(row["enabled"]):
        raise ValueError(f"标的 {symbol} 未启用")
    fund_code = (row["fund_code"] or "").strip()
    if not fund_code:
        raise ValueError(f"标的 {symbol} 缺少 fund_code 配置")
    return fund_code


def backfill_symbol_prices(
    conn,
    settings: dict[str, Any],
    symbol: str,
    start_date: str,
    end_date: str,
) -> BackfillResult:
    try:
        fund_code = _resolve_fund_code(conn, symbol)
    except ValueError as exc:
        return BackfillResult(
            symbol=symbol,
            success=False,
            rows=0,
            start_date=start_date,
            end_date=end_date,
            message=str(exc),
        )

    collector = AkshareCollector()
    try:
        df = collector.fetch_history(symbol, fund_code, start_date, end_date)
    except Exception as exc:
        message = str(exc)
        if "empty" in message.lower() or "no valid" in message.lower():
            return BackfillResult(
                symbol=symbol,
                success=True,
                rows=0,
                start_date=start_date,
                end_date=end_date,
                message=f"未获取到可用历史行情：{message}",
            )
        if is_connection_error(exc) and build_network_hint(exc) not in message:
            message = f"{message}。{build_network_hint(exc)}"
        return BackfillResult(
            symbol=symbol,
            success=False,
            rows=0,
            start_date=start_date,
            end_date=end_date,
            message=f"AKShare 拉取失败：{message}",
        )

    rows = upsert_daily_prices(conn, df)
    actual_start = str(df["trade_date"].iloc[0]) if not df.empty else start_date
    actual_end = str(df["trade_date"].iloc[-1]) if not df.empty else end_date
    return BackfillResult(
        symbol=symbol,
        success=True,
        rows=rows,
        start_date=actual_start,
        end_date=actual_end,
        message=f"已写入 {rows} 条行情",
    )


def backfill_all_prices(
    conn,
    settings: dict[str, Any],
    start_date: str,
    end_date: str,
) -> list[BackfillResult]:
    results: list[BackfillResult] = []
    etfs = list_priceable_etfs(conn)

    for etf in etfs:
        symbol = etf["symbol"]
        result = backfill_symbol_prices(conn, settings, symbol, start_date, end_date)
        results.append(result)
        if result.success:
            logger.info("{}: {}", symbol, result.message)
        else:
            logger.warning("{}: {}", symbol, result.message)
    return results
