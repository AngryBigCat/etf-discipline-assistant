from __future__ import annotations


def calc_account_totals(cash_value: float, etf_market_value: float) -> dict:
    """Compute account-level totals. Never raises on zero/negative account value."""
    cash_value = float(cash_value or 0)
    etf_market_value = float(etf_market_value or 0)
    current_account_value = etf_market_value + cash_value

    if current_account_value <= 0:
        return {
            "cash_value": cash_value,
            "etf_market_value": etf_market_value,
            "current_account_value": 0.0,
            "total_position": 0.0,
            "cash_position": 0.0,
            "valid": False,
        }

    return {
        "cash_value": cash_value,
        "etf_market_value": etf_market_value,
        "current_account_value": current_account_value,
        "total_position": etf_market_value / current_account_value,
        "cash_position": cash_value / current_account_value,
        "valid": True,
    }


def calc_holding_metrics(
    market_value: float,
    cost: float,
    current_account_value: float,
) -> dict:
    market_value = float(market_value or 0)
    cost = float(cost or 0)
    profit_loss = market_value - cost
    profit_loss_rate = profit_loss / cost if cost > 0 else None
    weight = market_value / current_account_value if current_account_value > 0 else 0.0
    return {
        "market_value": market_value,
        "profit_loss": profit_loss,
        "profit_loss_rate": profit_loss_rate,
        "weight": weight,
    }


def calc_max_allowed_value(
    total_plan_amount: float,
    current_account_value: float,
    max_weight: float,
) -> float:
    plan_cap = float(total_plan_amount or 0) * float(max_weight or 0)
    account_cap = float(current_account_value or 0) * float(max_weight or 0)
    return min(plan_cap, account_cap)
