from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EXECUTION_MANUAL = "manual"
EXECUTION_MATCHED = "matched_signal"
EXECUTION_DEVIATED = "deviated"
EXECUTION_IGNORED = "ignored"
EXECUTION_RECORDED = "recorded"

TRADE_ACTION_BUY = "buy"
TRADE_ACTION_SELL = "sell"
TRADE_ACTION_HOLD = "hold"
TRADE_ACTION_IGNORE = "ignore"
TRADE_ACTION_ADJUST = "adjust"

SIGNAL_BUY_ACTIONS = {"strong_buy", "small_buy", "fixed_invest"}
SIGNAL_NO_BUY_ACTIONS = {"hold", "stop_buy"}


@dataclass
class DisciplineResult:
    is_rule_based: bool
    execution_status: str
    deviation_amount: float
    suggested_amount: float


def calc_deviation_amount(amount: float, suggested_amount: float) -> float:
    return float(amount or 0) - float(suggested_amount or 0)


def check_discipline(
    *,
    trade_action: str,
    amount: float,
    signal: dict[str, Any] | None = None,
    signal_id: int | None = None,
    user_is_rule_based: bool = False,
) -> DisciplineResult:
    suggested_amount = float((signal or {}).get("suggested_amount") or 0)
    amount = float(amount or 0)

    if signal_id is None and signal is None:
        return DisciplineResult(
            is_rule_based=bool(user_is_rule_based),
            execution_status=EXECUTION_MANUAL,
            deviation_amount=calc_deviation_amount(amount, suggested_amount),
            suggested_amount=suggested_amount,
        )

    if trade_action == TRADE_ACTION_IGNORE:
        return DisciplineResult(
            is_rule_based=True,
            execution_status=EXECUTION_IGNORED,
            deviation_amount=0.0,
            suggested_amount=suggested_amount,
        )

    if trade_action == TRADE_ACTION_HOLD:
        return DisciplineResult(
            is_rule_based=True,
            execution_status=EXECUTION_MATCHED,
            deviation_amount=calc_deviation_amount(amount, suggested_amount),
            suggested_amount=suggested_amount,
        )

    if trade_action == TRADE_ACTION_BUY and signal is not None:
        signal_action = str(signal.get("action") or "")
        if signal_action in SIGNAL_BUY_ACTIONS:
            if amount <= suggested_amount * 1.2:
                return DisciplineResult(
                    is_rule_based=True,
                    execution_status=EXECUTION_MATCHED,
                    deviation_amount=calc_deviation_amount(amount, suggested_amount),
                    suggested_amount=suggested_amount,
                )
            return DisciplineResult(
                is_rule_based=False,
                execution_status=EXECUTION_DEVIATED,
                deviation_amount=calc_deviation_amount(amount, suggested_amount),
                suggested_amount=suggested_amount,
            )
        if signal_action in SIGNAL_NO_BUY_ACTIONS and amount > 0:
            return DisciplineResult(
                is_rule_based=False,
                execution_status=EXECUTION_DEVIATED,
                deviation_amount=calc_deviation_amount(amount, suggested_amount),
                suggested_amount=suggested_amount,
            )

    if trade_action == TRADE_ACTION_SELL:
        return DisciplineResult(
            is_rule_based=bool(user_is_rule_based),
            execution_status=EXECUTION_RECORDED,
            deviation_amount=calc_deviation_amount(amount, suggested_amount),
            suggested_amount=suggested_amount,
        )

    return DisciplineResult(
        is_rule_based=bool(user_is_rule_based),
        execution_status=EXECUTION_RECORDED,
        deviation_amount=calc_deviation_amount(amount, suggested_amount),
        suggested_amount=suggested_amount,
    )
