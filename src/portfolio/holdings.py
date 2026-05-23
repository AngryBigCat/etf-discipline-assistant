from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from src.db.repository import save_account_snapshot, save_holding_snapshots
from src.portfolio.position import calc_account_totals, calc_holding_metrics


@dataclass
class HoldingInput:
    symbol: str
    quantity: float = 0.0
    cost: float = 0.0
    manual_market_value: float | None = None


@dataclass
class HoldingRecord:
    symbol: str
    quantity: float
    cost: float
    market_value: float
    profit_loss: float
    profit_loss_rate: float | None
    weight: float
    latest_price: float | None = None


def resolve_market_value(
    quantity: float,
    latest_price: float | None,
    manual_market_value: float | None = None,
) -> float | None:
    qty = float(quantity or 0)
    if latest_price is not None and qty > 0:
        return round(qty * float(latest_price), 2)
    if manual_market_value is not None and manual_market_value > 0:
        return round(float(manual_market_value), 2)
    if qty == 0:
        return 0.0
    return None


def build_holding_records(
    inputs: list[HoldingInput],
    price_map: dict[str, float],
    current_account_value: float,
) -> list[HoldingRecord]:
    records: list[HoldingRecord] = []
    for item in inputs:
        if item.symbol == "CASH":
            continue
        latest_price = price_map.get(item.symbol)
        market_value = resolve_market_value(item.quantity, latest_price, item.manual_market_value)
        if market_value is None:
            continue
        metrics = calc_holding_metrics(market_value, item.cost, current_account_value)
        records.append(
            HoldingRecord(
                symbol=item.symbol,
                quantity=float(item.quantity or 0),
                cost=float(item.cost or 0),
                market_value=metrics["market_value"],
                profit_loss=metrics["profit_loss"],
                profit_loss_rate=metrics["profit_loss_rate"],
                weight=metrics["weight"],
                latest_price=latest_price,
            )
        )
    return records


def save_snapshot(
    conn: sqlite3.Connection,
    snapshot_date: str,
    cash_value: float,
    inputs: list[HoldingInput],
    price_map: dict[str, float],
) -> dict[str, Any]:
    """Save account + holding snapshots. CASH is never written to holding_snapshot."""
    preliminary_etf_value = 0.0
    resolved: list[tuple[HoldingInput, float]] = []
    for item in inputs:
        if item.symbol == "CASH":
            continue
        latest_price = price_map.get(item.symbol)
        market_value = resolve_market_value(item.quantity, latest_price, item.manual_market_value)
        if market_value is None:
            continue
        resolved.append((item, market_value))
        preliminary_etf_value += market_value

    account_totals = calc_account_totals(cash_value, preliminary_etf_value)
    current_account_value = float(account_totals["current_account_value"])

    holding_rows: list[dict[str, Any]] = []
    for item, market_value in resolved:
        metrics = calc_holding_metrics(market_value, item.cost, current_account_value)
        holding_rows.append(
            {
                "symbol": item.symbol,
                "quantity": float(item.quantity or 0),
                "cost": float(item.cost or 0),
                "market_value": metrics["market_value"],
                "profit_loss": metrics["profit_loss"],
                "profit_loss_rate": metrics["profit_loss_rate"],
                "weight": metrics["weight"],
            }
        )

    save_account_snapshot(
        conn,
        {
            "snapshot_date": snapshot_date,
            "cash_value": account_totals["cash_value"],
            "etf_market_value": account_totals["etf_market_value"],
            "total_account_value": account_totals["current_account_value"],
            "total_position": account_totals["total_position"],
            "cash_position": account_totals["cash_position"],
        },
    )
    save_holding_snapshots(conn, snapshot_date, holding_rows)

    return {
        "snapshot_date": snapshot_date,
        "account": account_totals,
        "holdings_count": len(holding_rows),
    }
