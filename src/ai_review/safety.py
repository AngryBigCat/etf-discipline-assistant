from __future__ import annotations

import copy
import re
from typing import Any

RISK_DISCLAIMER = "本内容不构成投资建议。"

DANGEROUS_WORDS = ("保证收益", "必涨", "必买", "稳赚", "包赚")

# 「满仓」仅在有明确建议语义时屏蔽；「不要满仓 / 避免满仓」等风险提示放行。
FULL_POSITION_DANGEROUS_PHRASES = ("建议满仓", "可以满仓", "必须满仓", "直接满仓")
FULL_POSITION_SAFE_PREFIXES = ("不要", "避免", "勿", "禁止", "不可", "不能", "不应", "不该", "不得")

TRADING_ADVICE_REWRITES: tuple[tuple[str, str], ...] = (
    ("建议买入", "系统信号显示可关注，最终需人工确认"),
    ("建议卖出", "建议检查该仓位是否偏离规则，最终需人工确认"),
    ("建议加仓", "建议关注仓位是否低于规则目标，最终需人工确认"),
    ("建议补仓", "建议关注仓位偏离情况，等待系统信号并人工确认"),
    ("建议减仓", "建议检查是否超过规则仓位上限，最终需人工确认"),
    ("应该买入", "不应由 AI 直接给出买入结论，请以系统规则和人工确认为准"),
    ("应该卖出", "不应由 AI 直接给出卖出结论，请以系统规则和人工确认为准"),
)

SENSITIVE_KEYS = {"api_key", "database_path", "note", "settings", "input_snapshot"}


def _find_full_position_hits(text: str) -> list[str]:
    hits: list[str] = []
    for phrase in FULL_POSITION_DANGEROUS_PHRASES:
        start = 0
        while True:
            idx = text.find(phrase, start)
            if idx == -1:
                break
            before = text[:idx]
            if not any(before.endswith(prefix) for prefix in FULL_POSITION_SAFE_PREFIXES):
                hits.append(phrase)
            start = idx + len(phrase)
    return hits


def rewrite_trading_advice_phrases(text: str) -> str:
    cleaned = text or ""
    for source, target in TRADING_ADVICE_REWRITES:
        cleaned = cleaned.replace(source, target)
    return cleaned


def append_risk_disclaimer(text: str) -> str:
    if not text:
        return RISK_DISCLAIMER
    if "不构成投资建议" in text:
        return text
    return f"{text.rstrip()}\n\n{RISK_DISCLAIMER}"


def validate_ai_review_output(text: str) -> tuple[str, str, str]:
    cleaned = rewrite_trading_advice_phrases(text or "")
    hit_words = [word for word in DANGEROUS_WORDS if word in cleaned]
    hit_words.extend(_find_full_position_hits(cleaned))
    if hit_words:
        for word in dict.fromkeys(hit_words):
            cleaned = cleaned.replace(word, "[已屏蔽]")
        cleaned = append_risk_disclaimer(cleaned)
        return cleaned, "blocked", f"检测到危险表述：{', '.join(dict.fromkeys(hit_words))}"
    cleaned = append_risk_disclaimer(cleaned)
    return cleaned, "success", ""


def _round_large_numbers(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if abs(value) >= 10000:
            return round(value / 100) * 100
        return value
    if isinstance(value, dict):
        return {k: _round_large_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_round_large_numbers(v) for v in value]
    if isinstance(value, str):
        if re.search(r"[A-Za-z]:\\|/Users/|DATABASE_PATH|api_key", value):
            return "[已隐藏]"
        return value
    return value


def sanitize_prompt_context(context: dict[str, Any]) -> dict[str, Any]:
    sanitized = copy.deepcopy(context)
    for key in list(sanitized.keys()):
        if key in SENSITIVE_KEYS:
            sanitized.pop(key, None)
    report_key = "daily_report" if "daily_report" in sanitized else "weekly_report"
    if report_key in sanitized and isinstance(sanitized[report_key], dict):
        report = sanitized[report_key]
        sanitized[report_key] = {
            "summary": (report.get("summary") or "")[:800],
            "risk_warning": (report.get("risk_warning") or "")[:800],
            "action_suggestion": (report.get("action_suggestion") or "")[:800],
            "discipline_summary": (report.get("discipline_summary") or "")[:800],
            "risk_summary": (report.get("risk_summary") or "")[:800],
        }
    return _round_large_numbers(sanitized)
