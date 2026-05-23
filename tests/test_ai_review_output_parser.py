from __future__ import annotations

import sqlite3

import pytest

from src.ai_review.output_parser import build_review_display, extract_sections


def test_extract_sections_markdown_h2_behavior():
    text = "## 行为发现\n\n- 当日存在临时决策\n\n## 风险提醒\n\n- 仓位偏高"
    sections = extract_sections(text)
    assert sections["行为发现"] == "- 当日存在临时决策"
    assert sections["风险提醒"] == "- 仓位偏高"


def test_extract_sections_colon_behavior():
    text = "行为发现：\n- 追涨 1 次\n\n风险提醒：\n- 注意现金缓冲"
    sections = extract_sections(text)
    assert sections["行为发现"] == "- 追涨 1 次"
    assert sections["风险提醒"] == "- 注意现金缓冲"


def test_build_review_display_prefers_behavior_findings_column():
    review = {
        "discipline_summary": "DB 纪律总结",
        "behavior_findings": "- DB 行为发现",
        "risk_summary": "DB 风险",
        "action_suggestion": "DB 建议",
        "output_text": "## 行为发现\n\n- 文本行为发现",
    }
    display = build_review_display(review, weekly=False)
    assert display["behavior"] == "- DB 行为发现"
    assert display["discipline_summary"] == "DB 纪律总结"


def test_build_review_display_separates_raw_output():
    review = {
        "discipline_summary": "纪律总结内容",
        "behavior_findings": "- 行为 1",
        "risk_summary": "风险内容",
        "action_suggestion": "建议内容",
        "output_text": "### 纪律总结\n\n纪律总结内容\n\n### 行为发现\n\n- 行为 1",
    }
    display = build_review_display(review)
    assert display["raw_output"].startswith("### 纪律总结")
    assert display["discipline_summary"] == "纪律总结内容"
    assert display["behavior"] == "- 行为 1"
    assert display["discipline_summary"] not in display["raw_output"] or display["raw_output"]


def test_build_review_display_falls_back_to_output_text_sections():
    review = {
        "discipline_summary": "",
        "behavior_findings": "",
        "risk_summary": "",
        "action_suggestion": "",
        "output_text": "行为发现：\n- 从文本解析",
    }
    display = build_review_display(review)
    assert display["behavior"] == "- 从文本解析"
