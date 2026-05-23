from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.db.repository import (
    get_recent_trade_logs,
    get_trade_logs,
    save_trade_log,
    update_strategy_signal_review_status,
)
from src.trading.discipline_checker import (
    TRADE_ACTION_BUY,
    TRADE_ACTION_IGNORE,
    check_discipline,
)
from src.utils.date_utils import today_str


@dataclass
class TradeLogInput:
    trade_date: str
    symbol: str
    action: str
    amount: float
    price: float | None = None
    quantity: float | None = None
    reason: str = ""
    emotion: str = "planned"
    note: str = ""
    signal_id: int | None = None
    user_is_rule_based: bool = False


def calc_quantity(amount: float, price: float | None) -> float | None:
    if price is None or price <= 0:
        return None
    return float(amount) / float(price)


def build_trade_log_row(
    trade_input: TradeLogInput,
    signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    discipline = check_discipline(
        trade_action=trade_input.action,
        amount=trade_input.amount,
        signal=signal,
        signal_id=trade_input.signal_id,
        user_is_rule_based=trade_input.user_is_rule_based,
    )
    quantity = trade_input.quantity
    if quantity is None and trade_input.price:
        quantity = calc_quantity(trade_input.amount, trade_input.price)

    return {
        "trade_date": trade_input.trade_date,
        "symbol": trade_input.symbol,
        "signal_id": trade_input.signal_id,
        "action": trade_input.action,
        "amount": float(trade_input.amount or 0),
        "price": trade_input.price,
        "quantity": quantity,
        "reason": trade_input.reason or None,
        "emotion": trade_input.emotion or None,
        "is_rule_based": 1 if discipline.is_rule_based else 0,
        "suggested_amount": discipline.suggested_amount,
        "deviation_amount": discipline.deviation_amount,
        "execution_status": discipline.execution_status,
        "note": trade_input.note or None,
    }


def create_buy_from_signal(
    conn,
    signal_row: dict[str, Any],
    *,
    trade_date: str | None = None,
    amount: float | None = None,
    price: float | None = None,
    quantity: float | None = None,
    reason: str = "",
    emotion: str = "planned",
    note: str = "",
) -> int:
    suggested = float(signal_row.get("suggested_amount") or 0)
    actual_amount = float(amount if amount is not None else suggested)
    actual_price = price
    actual_quantity = quantity
    if actual_quantity is None and actual_price:
        actual_quantity = calc_quantity(actual_amount, actual_price)

    trade_input = TradeLogInput(
        trade_date=trade_date or today_str(),
        symbol=str(signal_row["symbol"]),
        action=TRADE_ACTION_BUY,
        amount=actual_amount,
        price=actual_price,
        quantity=actual_quantity,
        reason=reason,
        emotion=emotion,
        note=note,
        signal_id=int(signal_row["id"]),
    )
    row = build_trade_log_row(trade_input, signal=signal_row)
    trade_id = save_trade_log(conn, row)
    update_strategy_signal_review_status(conn, int(signal_row["id"]), "executed")
    return trade_id


def create_ignore_from_signal(
    conn,
    signal_row: dict[str, Any],
    *,
    trade_date: str | None = None,
    reason: str = "忽略策略信号",
    note: str = "",
) -> int:
    trade_input = TradeLogInput(
        trade_date=trade_date or today_str(),
        symbol=str(signal_row["symbol"]),
        action=TRADE_ACTION_IGNORE,
        amount=0.0,
        reason=reason,
        emotion="planned",
        note=note,
        signal_id=int(signal_row["id"]),
    )
    row = build_trade_log_row(trade_input, signal=signal_row)
    trade_id = save_trade_log(conn, row)
    update_strategy_signal_review_status(conn, int(signal_row["id"]), "ignored")
    return trade_id


def create_manual_trade(conn, trade_input: TradeLogInput) -> int:
    row = build_trade_log_row(trade_input, signal=None)
    return save_trade_log(conn, row)


def mark_signal_reviewed(conn, signal_id: int) -> None:
    update_strategy_signal_review_status(conn, signal_id, "reviewed")


def get_trade_summary(
    conn,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    if end_date is None:
        end_date = today_str()
    if start_date is None:
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )

    rows = get_trade_logs(conn, start_date=start_date, end_date=end_date)
    total_count = len(rows)
    buy_count = sum(1 for row in rows if row["action"] == TRADE_ACTION_BUY)
    sell_count = sum(1 for row in rows if row["action"] == "sell")
    rule_based_count = sum(1 for row in rows if row["is_rule_based"])
    not_rule_based_count = total_count - rule_based_count
    chasing_count = sum(1 for row in rows if row["emotion"] == "chasing")
    panic_count = sum(1 for row in rows if row["emotion"] == "panic")
    temporary_count = sum(1 for row in rows if row["emotion"] == "temporary")
    total_buy_amount = sum(float(row["amount"] or 0) for row in rows if row["action"] == TRADE_ACTION_BUY)
    total_sell_amount = sum(float(row["amount"] or 0) for row in rows if row["action"] == "sell")
    compliance_rate = rule_based_count / total_count if total_count else 0.0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_count": total_count,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "rule_based_count": rule_based_count,
        "not_rule_based_count": not_rule_based_count,
        "compliance_rate": compliance_rate,
        "chasing_count": chasing_count,
        "panic_count": panic_count,
        "temporary_count": temporary_count,
        "total_buy_amount": total_buy_amount,
        "total_sell_amount": total_sell_amount,
    }
