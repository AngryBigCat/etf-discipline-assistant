from __future__ import annotations

import hashlib
import json
from typing import Any

from src.ai_review.context_builder import (
    build_daily_review_context,
    build_weekly_review_context,
)
from src.ai_review.llm_client import BaseLLMClient, get_llm_client
from src.ai_review.prompt_builder import (
    PROMPT_VERSION,
    build_daily_review_prompt,
    build_weekly_review_prompt,
    dumps_context_for_snapshot,
)
from src.ai_review.safety import sanitize_prompt_context, validate_ai_review_output
from src.db.repository import upsert_ai_review


def _parse_json_output(text: str) -> dict[str, Any]:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def _join_list(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)
    if value is None:
        return ""
    return str(value)


def _compose_output_text(parsed: dict[str, Any], raw_text: str) -> str:
    if not parsed:
        return raw_text
    parts = [
        f"### 纪律总结\n\n{parsed.get('discipline_summary') or ''}",
        f"### 行为发现\n\n{_join_list(parsed.get('behavior_findings'))}",
        f"### 风险提醒\n\n{_join_list(parsed.get('risk_summary'))}",
        f"### 纪律建议\n\n{_join_list(parsed.get('action_suggestion'))}",
        f"### 说明\n\n{parsed.get('final_note') or ''}",
    ]
    return "\n\n".join(part for part in parts if part.strip())


def _build_review_row(
    *,
    review_type: str,
    target_date: str,
    week_start: str,
    week_end: str,
    source_type: str,
    source_digest: str,
    prompt_version: str,
    provider: str,
    model: str | None,
    input_snapshot: str,
    output_text: str,
    parsed: dict[str, Any],
    status: str,
    error_message: str,
) -> dict[str, Any]:
    return {
        "review_type": review_type,
        "target_date": target_date or "",
        "week_start": week_start or "",
        "week_end": week_end or "",
        "source_type": source_type,
        "source_digest": source_digest,
        "prompt_version": prompt_version or PROMPT_VERSION,
        "provider": provider,
        "model": model,
        "input_snapshot": input_snapshot,
        "output_text": output_text,
        "discipline_summary": str(parsed.get("discipline_summary") or ""),
        "risk_summary": _join_list(parsed.get("risk_summary")),
        "action_suggestion": _join_list(parsed.get("action_suggestion")),
        "status": status,
        "error_message": error_message,
    }


def generate_daily_ai_review(
    conn,
    settings: dict[str, Any],
    target_date: str,
    *,
    client: BaseLLMClient | None = None,
    prompt_version: str = PROMPT_VERSION,
) -> tuple[dict[str, Any] | None, bool, str]:
    context = build_daily_review_context(conn, settings, target_date)
    if context.get("missing"):
        return None, False, str(context.get("message") or "无法构建日复盘上下文")

    sanitized = sanitize_prompt_context(context)
    prompt = build_daily_review_prompt(sanitized)
    llm = client or get_llm_client()
    raw = llm.complete(prompt["system"], prompt["user"])

    parsed = _parse_json_output(raw.get("text", ""))
    composed = _compose_output_text(parsed, raw.get("text", ""))
    output_text, safety_status, safety_error = validate_ai_review_output(composed)

    status = safety_status
    error_message = safety_error
    if raw.get("status") == "failed":
        status = "failed"
        error_message = str(raw.get("error_message") or safety_error)

    report = context["daily_report"]
    source_digest = hashlib.sha256((report.get("summary") or "").encode("utf-8")).hexdigest()[:16]
    row = _build_review_row(
        review_type="daily",
        target_date=target_date,
        week_start="",
        week_end="",
        source_type="daily_report",
        source_digest=source_digest,
        prompt_version=prompt_version,
        provider=str(raw.get("provider") or getattr(llm, "provider", "mock")),
        model=raw.get("model") or getattr(llm, "model", None),
        input_snapshot=dumps_context_for_snapshot(sanitized)[:8000],
        output_text=output_text,
        parsed=parsed,
        status=status,
        error_message=error_message,
    )
    upsert_ai_review(conn, row)
    return row, True, "AI 日复盘已生成"


def generate_weekly_ai_review(
    conn,
    settings: dict[str, Any],
    week_start: str,
    week_end: str,
    *,
    client: BaseLLMClient | None = None,
    prompt_version: str = PROMPT_VERSION,
) -> tuple[dict[str, Any] | None, bool, str]:
    context = build_weekly_review_context(conn, settings, week_start, week_end)
    if context.get("missing"):
        return None, False, str(context.get("message") or "无法构建周复盘上下文")

    sanitized = sanitize_prompt_context(context)
    prompt = build_weekly_review_prompt(sanitized)
    llm = client or get_llm_client()
    raw = llm.complete(prompt["system"], prompt["user"])

    parsed = _parse_json_output(raw.get("text", ""))
    composed = _compose_output_text(parsed, raw.get("text", ""))
    output_text, safety_status, safety_error = validate_ai_review_output(composed)

    status = safety_status
    error_message = safety_error
    if raw.get("status") == "failed":
        status = "failed"
        error_message = str(raw.get("error_message") or safety_error)

    report = context["weekly_report"]
    source_digest = hashlib.sha256((report.get("summary") or "").encode("utf-8")).hexdigest()[:16]
    row = _build_review_row(
        review_type="weekly",
        target_date="",
        week_start=week_start,
        week_end=week_end,
        source_type="weekly_report",
        source_digest=source_digest,
        prompt_version=prompt_version,
        provider=str(raw.get("provider") or getattr(llm, "provider", "mock")),
        model=raw.get("model") or getattr(llm, "model", None),
        input_snapshot=dumps_context_for_snapshot(sanitized)[:8000],
        output_text=output_text,
        parsed=parsed,
        status=status,
        error_message=error_message,
    )
    upsert_ai_review(conn, row)
    return row, True, "AI 周复盘已生成"
