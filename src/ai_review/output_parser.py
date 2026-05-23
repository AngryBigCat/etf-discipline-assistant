from __future__ import annotations

import re
from typing import Any

from src.ai_review.safety import rewrite_trading_advice_phrases

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "纪律总结": ("纪律总结",),
    "行为发现": ("行为发现", "行为模式"),
    "风险提醒": ("风险提醒", "风险总结"),
    "纪律建议": ("纪律建议", "下个交易日纪律建议", "下周纪律建议"),
    "说明": ("说明",),
}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical for canonical, aliases in SECTION_ALIASES.items() for alias in aliases
}

_SORTED_ALIASES = sorted(_ALIAS_TO_CANONICAL, key=len, reverse=True)
_ALIAS_PATTERN = "|".join(re.escape(alias) for alias in _SORTED_ALIASES)

_MARKDOWN_HEADER_RE = re.compile(
    rf"^(#{{1,3}})\s*({_ALIAS_PATTERN})\s*\n+(.*?)(?=^#{{1,3}}\s|\Z)",
    re.MULTILINE | re.DOTALL,
)

_COLON_HEADER_RE = re.compile(
    rf"^({_ALIAS_PATTERN})[：:]\s*\n?(.*?)(?=^({_ALIAS_PATTERN})[：:]|^#{{1,3}}\s|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _normalize_review(review: dict[str, Any] | Any) -> dict[str, Any]:
    if hasattr(review, "keys") and not isinstance(review, dict):
        return dict(review)
    return dict(review or {})


def extract_sections(text: str | None) -> dict[str, str]:
    if not text:
        return {}

    sections: dict[str, str] = {}

    for match in _MARKDOWN_HEADER_RE.finditer(text):
        canonical = _ALIAS_TO_CANONICAL.get(match.group(2).strip())
        if canonical:
            sections[canonical] = match.group(3).strip()

    for match in _COLON_HEADER_RE.finditer(text):
        canonical = _ALIAS_TO_CANONICAL.get(match.group(1).strip())
        if canonical and canonical not in sections:
            sections[canonical] = match.group(2).strip()

    return sections


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return "—"


def _sanitize_display_text(value: str) -> str:
    if not value or value == "—":
        return value
    return rewrite_trading_advice_phrases(value)


def build_review_display(review: dict[str, Any] | Any, *, weekly: bool = False) -> dict[str, str]:
    row = _normalize_review(review)
    sections = extract_sections(row.get("output_text"))
    behavior_from_db = row.get("behavior_findings")

    display = {
        "discipline_summary": _first_non_empty(
            row.get("discipline_summary"),
            sections.get("纪律总结"),
        ),
        "behavior": _first_non_empty(
            behavior_from_db,
            sections.get("行为发现"),
        ),
        "risk_summary": _first_non_empty(
            row.get("risk_summary"),
            sections.get("风险提醒"),
        ),
        "action_suggestion": _first_non_empty(
            row.get("action_suggestion"),
            sections.get("纪律建议"),
        ),
        "final_note": _first_non_empty(sections.get("说明")),
        "behavior_title": "行为模式" if weekly else "行为发现",
        "action_title": "下周纪律建议" if weekly else "下个交易日纪律建议",
        "raw_output": str(row.get("output_text") or "").strip(),
    }
    for key in ("discipline_summary", "behavior", "risk_summary", "action_suggestion", "final_note", "raw_output"):
        display[key] = _sanitize_display_text(display[key])
    return display
