from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BASE_SCORE = 50.0
VOLATILITY_SCORE = 0.0


@dataclass
class ScoreBreakdown:
    base_score: float = BASE_SCORE
    trend_score: float = 0.0
    drawdown_score: float = 0.0
    anti_chase_score: float = 0.0
    position_score: float = 0.0
    special_score: float = 0.0
    volatility_score: float = VOLATILITY_SCORE
    final_score: float = BASE_SCORE
    reasons: list[str] = field(default_factory=list)
    force_stop_buy: bool = False
    confidence_level: str = "normal"


def _clamp_score(score: float) -> float:
    return max(0.0, min(100.0, score))


def calc_trend_score(
    close: float,
    ma60: float | None,
    ma120: float | None,
    ma250: float | None,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if ma60 is not None:
        if close > ma60:
            score += 10
            reasons.append("价格站上60日均线，短期趋势较好")
        else:
            score -= 8
            reasons.append("价格低于60日均线，短期趋势偏弱")

    if ma120 is not None:
        if close > ma120:
            score += 8
            reasons.append("价格站上120日均线，中期趋势较好")
        else:
            score -= 8
            reasons.append("价格低于120日均线，中期趋势偏弱")

    if ma250 is not None:
        if close > ma250:
            score += 8
            reasons.append("价格站上250日均线，长期趋势较好")
        else:
            score -= 8
            reasons.append("价格低于250日均线，长期趋势偏弱")

    return score, reasons


def calc_drawdown_score(
    drawdown_used: float | None,
    drawdown_window: int | None,
) -> tuple[float, list[str]]:
    if drawdown_used is None:
        return 0.0, []

    window = drawdown_window or 0
    score = 0.0
    reasons: list[str] = []

    if drawdown_used <= -0.15:
        score = 20
        reasons.append(f"近{window}日回撤超过15%，进入深度回撤区域")
    elif drawdown_used <= -0.10:
        score = 15
        reasons.append(f"近{window}日回撤超过10%，具备分批观察价值")
    elif drawdown_used <= -0.05:
        score = 10
        reasons.append(f"近{window}日回撤超过5%，触发补仓观察")
    elif drawdown_used <= -0.03:
        score = 5
        reasons.append(f"近{window}日回撤超过3%，可小额观察")

    return score, reasons


def calc_anti_chase_score(
    return_5d: float | None,
    return_10d: float | None,
    return_20d: float | None,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if return_5d is not None and return_5d >= 0.05:
        score -= 10
        reasons.append("近5日涨幅超过5%，存在追涨风险")

    if return_10d is not None and return_10d >= 0.08:
        score -= 15
        reasons.append("近10日涨幅超过8%，短期偏热")

    if return_20d is not None and return_20d >= 0.12:
        score -= 20
        reasons.append("近20日涨幅超过12%，短期过热")

    return score, reasons


def calc_position_score(
    weight: float,
    target_weight: float,
    market_value: float,
    max_allowed_value: float,
    total_position: float,
    cash_position: float,
) -> tuple[float, list[str], bool]:
    score = 0.0
    reasons: list[str] = []
    force_stop_buy = False

    if market_value > max_allowed_value:
        score -= 40
        force_stop_buy = True
        reasons.append("当前持仓超过最大允许市值，禁止继续加仓")
    elif weight > target_weight:
        score -= 15
        reasons.append("当前仓位高于目标仓位，降低买入优先级")
    elif weight < target_weight * 0.7:
        score += 10
        reasons.append("当前仓位低于目标仓位，可作为补仓候选")

    if total_position > 0.80:
        score -= 30
        force_stop_buy = True
        reasons.append("总ETF仓位超过80%，禁止继续加仓")
    elif total_position > 0.70:
        score -= 15
        reasons.append("总ETF仓位超过70%，降低买入强度")

    if cash_position < 0.20:
        score -= 25
        reasons.append("现金仓位低于20%，需要保留备用资金")

    return score, reasons, force_stop_buy


def calc_special_score(
    symbol: str,
    weight: float,
    close: float,
    ma120: float | None,
    return_5d: float | None,
) -> tuple[float, list[str], bool]:
    if symbol != "KC50":
        return 0.0, [], False

    score = 0.0
    reasons: list[str] = []
    force_stop_buy = False

    if weight >= 0.20:
        force_stop_buy = True
        reasons.append("科创50仓位达到20%上限，强制暂停买入")

    if weight >= 0.18:
        score -= 20
        reasons.append("科创50仓位接近20%上限，暂停主动加仓")

    if return_5d is not None and return_5d >= 0.05:
        score -= 15
        reasons.append("科创50短期涨幅较大，禁止追买")

    if ma120 is not None and close < ma120:
        score -= 10
        reasons.append("科创50低于120日均线，只允许观察或小额定投")

    return score, reasons, force_stop_buy


def compute_score(
    *,
    close: float,
    indicator: dict[str, Any],
    asset: dict[str, Any],
    position: dict[str, Any],
    portfolio: dict[str, Any],
    max_allowed_value: float,
) -> ScoreBreakdown:
    confidence_level = str(indicator.get("confidence_level") or "normal")
    reasons: list[str] = []

    trend_score, trend_reasons = calc_trend_score(
        close=close,
        ma60=indicator.get("ma60"),
        ma120=indicator.get("ma120"),
        ma250=indicator.get("ma250"),
    )
    reasons.extend(trend_reasons)

    if indicator.get("ma250") is None:
        reasons.append("250日均线数据不足，跳过250日均线趋势打分")

    drawdown_score, drawdown_reasons = calc_drawdown_score(
        drawdown_used=indicator.get("drawdown_used"),
        drawdown_window=indicator.get("drawdown_window"),
    )
    reasons.extend(drawdown_reasons)

    if confidence_level == "low":
        reasons.append("指标数据置信度偏低，请谨慎参考")

    anti_chase_score, anti_reasons = calc_anti_chase_score(
        return_5d=indicator.get("return_5d"),
        return_10d=indicator.get("return_10d"),
        return_20d=indicator.get("return_20d"),
    )
    reasons.extend(anti_reasons)

    position_score, position_reasons, position_force_stop = calc_position_score(
        weight=float(position.get("weight") or 0),
        target_weight=float(asset.get("target_weight") or 0),
        market_value=float(position.get("market_value") or 0),
        max_allowed_value=max_allowed_value,
        total_position=float(portfolio.get("total_position") or 0),
        cash_position=float(portfolio.get("cash_position") or 0),
    )
    reasons.extend(position_reasons)

    special_score, special_reasons, special_force_stop = calc_special_score(
        symbol=str(asset.get("symbol") or ""),
        weight=float(position.get("weight") or 0),
        close=close,
        ma120=indicator.get("ma120"),
        return_5d=indicator.get("return_5d"),
    )
    reasons.extend(special_reasons)

    force_stop_buy = position_force_stop or special_force_stop
    raw_final = (
        BASE_SCORE
        + trend_score
        + drawdown_score
        + anti_chase_score
        + position_score
        + special_score
        + VOLATILITY_SCORE
    )

    return ScoreBreakdown(
        base_score=BASE_SCORE,
        trend_score=trend_score,
        drawdown_score=drawdown_score,
        anti_chase_score=anti_chase_score,
        position_score=position_score,
        special_score=special_score,
        volatility_score=VOLATILITY_SCORE,
        final_score=_clamp_score(raw_final),
        reasons=reasons,
        force_stop_buy=force_stop_buy,
        confidence_level=confidence_level,
    )
