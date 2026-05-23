from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.portfolio.position import calc_max_allowed_value

STATUS_UNDERWEIGHT = "underweight"
STATUS_NORMAL = "normal"
STATUS_OVERWEIGHT = "overweight"
STATUS_EXCEED_MAX = "exceed_max"
STATUS_WATCH_ONLY = "watch_only"


@dataclass
class PositionRow:
    symbol: str
    name: str
    market_value: float
    cost: float
    profit_loss: float
    profit_loss_rate: float | None
    weight: float
    target_weight: float
    max_weight: float
    max_allowed_value: float
    deviation: float
    status: str
    enabled_for_signal: bool
    quantity: float = 0.0
    latest_price: float | None = None


def calc_deviation(weight: float, target_weight: float) -> float:
    return float(weight or 0) - float(target_weight or 0)


def classify_position(
    weight: float,
    target_weight: float,
    market_value: float,
    max_allowed_value: float,
    enabled_for_signal: bool,
) -> str:
    if not enabled_for_signal:
        return STATUS_WATCH_ONLY
    if market_value > max_allowed_value:
        return STATUS_EXCEED_MAX
    if weight > target_weight:
        return STATUS_OVERWEIGHT
    if weight < target_weight:
        return STATUS_UNDERWEIGHT
    return STATUS_NORMAL


def build_position_rows(
    holdings: list[dict[str, Any]],
    universe_map: dict[str, dict[str, Any]],
    total_plan_amount: float,
    account_totals: dict[str, Any],
) -> list[PositionRow]:
    current_account_value = float(account_totals.get("current_account_value") or 0)
    rows: list[PositionRow] = []

    for holding in holdings:
        symbol = holding["symbol"]
        meta = universe_map.get(symbol, {})
        enabled_for_signal = bool(meta.get("enabled_for_signal", True))
        target_weight = float(meta.get("target_weight") or 0)
        max_weight = float(meta.get("max_weight") or 0)
        market_value = float(holding.get("market_value") or 0)
        weight = float(holding.get("weight") or 0)
        max_allowed = calc_max_allowed_value(total_plan_amount, current_account_value, max_weight)
        status = classify_position(
            weight=weight,
            target_weight=target_weight,
            market_value=market_value,
            max_allowed_value=max_allowed,
            enabled_for_signal=enabled_for_signal,
        )
        rows.append(
            PositionRow(
                symbol=symbol,
                name=str(meta.get("name") or symbol),
                market_value=market_value,
                cost=float(holding.get("cost") or 0),
                profit_loss=float(holding.get("profit_loss") or 0),
                profit_loss_rate=holding.get("profit_loss_rate"),
                weight=weight,
                target_weight=target_weight,
                max_weight=max_weight,
                max_allowed_value=max_allowed,
                deviation=calc_deviation(weight, target_weight),
                status=status,
                enabled_for_signal=enabled_for_signal,
                quantity=float(holding.get("quantity") or 0),
                latest_price=holding.get("latest_price"),
            )
        )
    return rows


def build_alerts(position_rows: list[PositionRow]) -> list[str]:
    alerts: list[str] = []
    for row in position_rows:
        if row.status == STATUS_EXCEED_MAX:
            alerts.append(f"{row.symbol} 超过 max_weight 上限（当前 {row.market_value:.2f} > 允许 {row.max_allowed_value:.2f}）")
        elif row.status == STATUS_OVERWEIGHT:
            alerts.append(f"{row.symbol} 高于目标仓位（偏离 {row.deviation * 100:.1f}%）")
        elif row.status == STATUS_UNDERWEIGHT:
            alerts.append(f"{row.symbol} 低于目标仓位，可考虑优先补仓（偏离 {row.deviation * 100:.1f}%）")
    return alerts
