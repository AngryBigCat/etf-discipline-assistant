from __future__ import annotations

import copy
import re
from typing import Any

RISK_DISCLAIMER = "本内容不构成投资建议。"

DANGEROUS_WORDS = ("保证收益", "必涨", "必买", "满仓", "稳赚", "包赚")

SENSITIVE_KEYS = {"api_key", "database_path", "note", "settings", "input_snapshot"}


def append_risk_disclaimer(text: str) -> str:
    if not text:
        return RISK_DISCLAIMER
    if "不构成投资建议" in text:
        return text
    return f"{text.rstrip()}\n\n{RISK_DISCLAIMER}"


def validate_ai_review_output(text: str) -> tuple[str, str, str]:
    cleaned = text or ""
    hit_words = [word for word in DANGEROUS_WORDS if word in cleaned]
    if hit_words:
        for word in hit_words:
            cleaned = cleaned.replace(word, "[已屏蔽]")
        cleaned = append_risk_disclaimer(cleaned)
        return cleaned, "blocked", f"检测到危险表述：{', '.join(hit_words)}"
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
