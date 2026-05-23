from __future__ import annotations

from typing import Any

from src.portfolio.position import calc_max_allowed_value

ACTION_STRONG_BUY = "strong_buy"
ACTION_SMALL_BUY = "small_buy"
ACTION_FIXED_INVEST = "fixed_invest"
ACTION_HOLD = "hold"
ACTION_STOP_BUY = "stop_buy"

ACTION_MULTIPLIERS = {
    ACTION_STRONG_BUY: 1.0,
    ACTION_SMALL_BUY: 0.5,
    ACTION_FIXED_INVEST: 0.3,
    ACTION_HOLD: 0.0,
    ACTION_STOP_BUY: 0.0,
}

DEFAULT_ACTION_LABELS = {
    ACTION_STRONG_BUY: "可正常买入",
    ACTION_SMALL_BUY: "可小额买入",
    ACTION_FIXED_INVEST: "仅按定投计划",
    ACTION_HOLD: "观察，不主动买入",
    ACTION_STOP_BUY: "暂停买入",
}


def round_to_100(amount: float) -> float:
    if amount <= 0:
        return 0.0
    return float(round(amount / 100) * 100)


def build_reason_text(reasons: list[str]) -> str:
    return "；".join(reason for reason in reasons if reason)


def get_action_label(action: str, settings: dict[str, Any] | None = None) -> str:
    if settings:
        label = settings.get("actions", {}).get(action, {}).get("label")
        if label:
            return str(label)
    return DEFAULT_ACTION_LABELS.get(action, action)


def map_action(final_score: float, force_stop_buy: bool) -> str:
    if force_stop_buy:
        return ACTION_STOP_BUY
    if final_score >= 80:
        return ACTION_STRONG_BUY
    if final_score >= 65:
        return ACTION_SMALL_BUY
    if final_score >= 50:
        return ACTION_FIXED_INVEST
    if final_score >= 35:
        return ACTION_HOLD
    return ACTION_STOP_BUY


def calc_available_cash(
    cash_value: float,
    current_account_value: float,
    min_cash_position: float,
) -> float:
    reserved = current_account_value * min_cash_position
    return max(0.0, cash_value - reserved)


def calc_suggested_amount(
    *,
    action: str,
    asset: dict[str, Any],
    position: dict[str, Any],
    portfolio: dict[str, Any],
    settings: dict[str, Any],
    force_stop_buy: bool = False,
) -> float:
    if force_stop_buy or action in {ACTION_HOLD, ACTION_STOP_BUY}:
        return 0.0

    portfolio_cfg = settings.get("portfolio", {})
    total_plan_amount = float(portfolio_cfg.get("total_plan_amount") or 0)
    min_cash_position = float(portfolio_cfg.get("min_cash_position") or 0)
    current_account_value = float(portfolio.get("current_account_value") or 0)
    cash_value = float(portfolio.get("cash_value") or 0)
    total_position = float(portfolio.get("total_position") or 0)

    if total_position > 0.80:
        return 0.0

    base_amount = total_plan_amount * float(asset.get("single_buy_ratio") or 0)
    multiplier = ACTION_MULTIPLIERS.get(action, 0.0)
    amount = base_amount * multiplier

    if total_position > 0.70:
        amount *= 0.5

    max_allowed_value = calc_max_allowed_value(
        total_plan_amount,
        current_account_value,
        float(asset.get("max_weight") or 0),
    )
    market_value = float(position.get("market_value") or 0)
    remaining_capacity = max(0.0, max_allowed_value - market_value)
    amount = min(amount, remaining_capacity)

    available_cash = calc_available_cash(cash_value, current_account_value, min_cash_position)
    amount = min(amount, available_cash)

    if asset.get("symbol") == "KC50":
        kc50_limit = total_plan_amount * 0.02
        amount = min(amount, kc50_limit)

    return round_to_100(max(0.0, amount))
