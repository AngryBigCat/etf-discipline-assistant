from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sqlite3

from src.config.settings import get_signal_assets, get_watch_only_assets
from src.db.repository import (
    get_latest_indicators,
    get_latest_price_map,
    get_portfolio_overview,
    upsert_strategy_signals,
)
from src.portfolio.position import calc_max_allowed_value
from src.strategy.rule_engine import build_reason_text, calc_suggested_amount, map_action
from src.strategy.score_engine import compute_score
from src.utils.date_utils import today_str


class SnapshotRequiredError(Exception):
    """Raised when strategy signals cannot be generated without a valid snapshot."""


@dataclass
class StrategySignal:
    signal_date: str
    symbol: str
    name: str
    trend_score: float
    drawdown_score: float
    volatility_score: float
    position_score: float
    anti_chase_score: float
    special_score: float
    final_score: float
    action: str
    suggested_amount: float
    reason: str
    confidence_level: str
    review_status: str = "generated"
    id: int | None = None

    def to_db_row(self) -> dict[str, Any]:
        return {
            "signal_date": self.signal_date,
            "symbol": self.symbol,
            "trend_score": self.trend_score,
            "drawdown_score": self.drawdown_score,
            "volatility_score": self.volatility_score,
            "position_score": self.position_score,
            "anti_chase_score": self.anti_chase_score,
            "final_score": self.final_score,
            "action": self.action,
            "suggested_amount": self.suggested_amount,
            "reason": self.reason,
            "confidence_level": self.confidence_level,
            "review_status": self.review_status,
        }


def _build_position_map(positions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["symbol"]: row for row in positions}


def _default_position(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "market_value": 0.0,
        "weight": 0.0,
    }


def generate_signals(
    conn: sqlite3.Connection,
    settings: dict[str, Any],
    signal_date: str | None = None,
) -> tuple[list[StrategySignal], dict[str, Any]]:
    overview = get_portfolio_overview(conn, settings)
    account = overview["account"]
    if not account.get("valid"):
        raise SnapshotRequiredError("请先录入现金或 ETF 持仓后再生成策略信号")

    signal_date = signal_date or today_str()
    total_plan_amount = float(overview["total_plan_amount"])
    current_account_value = float(account["current_account_value"])
    position_map = _build_position_map(overview.get("positions") or [])

    indicators_df = get_latest_indicators(conn, enabled_only=False)
    indicator_map = {
        row["symbol"]: dict(row)
        for _, row in indicators_df.iterrows()
    } if not indicators_df.empty else {}
    close_map = get_latest_price_map(conn)

    signals: list[StrategySignal] = []
    for asset in get_signal_assets(settings):
        symbol = asset["symbol"]
        position = position_map.get(symbol, _default_position(symbol))
        indicator = indicator_map.get(symbol, {})
        close = close_map.get(symbol)

        if close is None:
            continue

        max_allowed_value = calc_max_allowed_value(
            total_plan_amount,
            current_account_value,
            float(asset.get("max_weight") or 0),
        )
        score = compute_score(
            close=float(close),
            indicator=indicator,
            asset=asset,
            position=position,
            portfolio=account,
            max_allowed_value=max_allowed_value,
        )
        action = map_action(score.final_score, score.force_stop_buy)
        suggested_amount = calc_suggested_amount(
            action=action,
            asset=asset,
            position=position,
            portfolio=account,
            settings=settings,
            force_stop_buy=score.force_stop_buy,
        )
        if score.force_stop_buy or action == "stop_buy":
            suggested_amount = 0.0

        signals.append(
            StrategySignal(
                signal_date=signal_date,
                symbol=symbol,
                name=str(asset.get("name") or symbol),
                trend_score=score.trend_score,
                drawdown_score=score.drawdown_score,
                volatility_score=score.volatility_score,
                position_score=score.position_score,
                anti_chase_score=score.anti_chase_score,
                special_score=score.special_score,
                final_score=score.final_score,
                action=action,
                suggested_amount=suggested_amount,
                reason=build_reason_text(score.reasons),
                confidence_level=score.confidence_level,
            )
        )

    context = {
        "signal_date": signal_date,
        "snapshot_date": overview.get("snapshot_date"),
        "account": account,
        "total_plan_amount": total_plan_amount,
        "watch_only_assets": get_watch_only_assets(settings),
    }
    return signals, context


def generate_and_save_signals(
    conn: sqlite3.Connection,
    settings: dict[str, Any],
    signal_date: str | None = None,
) -> tuple[list[StrategySignal], dict[str, Any]]:
    signals, context = generate_signals(conn, settings, signal_date=signal_date)
    upsert_strategy_signals(conn, [signal.to_db_row() for signal in signals])
    return signals, context
