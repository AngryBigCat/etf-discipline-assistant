from __future__ import annotations

import re
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.ai_review.output_parser import build_review_display
from src.ai_review.review_service import generate_daily_ai_review, generate_weekly_ai_review
from src.config.settings import load_settings
from src.db.connection import db_session, get_connection
from src.db.repository import get_latest_ai_reviews
from src.ui.labels import localize_ai_status, localize_review_type, rename_columns


def _preview(text: str | None, max_len: int = 80) -> str:
    if not text:
        return "—"
    plain = text.replace("\n", " ").strip()
    if len(plain) <= max_len:
        return plain
    return plain[:max_len] + "…"


def _render_review_sections(review: dict, *, weekly: bool = False) -> None:
    display = build_review_display(review, weekly=weekly)

    st.markdown("#### 纪律总结")
    st.markdown(display["discipline_summary"])

    st.markdown(f"#### {display['behavior_title']}")
    st.markdown(display["behavior"])

    st.markdown("#### 风险提醒")
    st.markdown(display["risk_summary"])

    st.markdown(f"#### {display['action_title']}")
    st.markdown(display["action_suggestion"])

    if display["final_note"] != "—":
        st.markdown("#### 说明")
        st.markdown(display["final_note"])

    if review.get("status") == "blocked":
        st.error(review.get("error_message") or "输出包含需屏蔽的表述。")
    elif review.get("status") == "failed":
        st.warning(review.get("error_message") or "AI 生成失败。")

    with st.expander("查看原始模型输出"):
        st.markdown(display["raw_output"] or "—")


def _render_history(rows: list) -> None:
    st.markdown("#### 历史 AI 复盘")
    preview_df = pd.DataFrame(
        [
            {
                "review_type": localize_review_type(row["review_type"]),
                "target_date": row["target_date"] or "—",
                "week_start": row["week_start"] or "—",
                "week_end": row["week_end"] or "—",
                "status": localize_ai_status(row["status"]),
                "preview": _preview(row["discipline_summary"] or row["output_text"], 60),
            }
            for row in rows
        ]
    )
    st.dataframe(rename_columns(preview_df), use_container_width=True, hide_index=True)

    for row in rows:
        item = dict(row)
        label = localize_review_type(item["review_type"])
        if item["review_type"] == "weekly":
            label += f" · {item['week_start']} ~ {item['week_end']}"
        else:
            label += f" · {item['target_date']}"
        label += f" · {_preview(item.get('discipline_summary'), 40)}"
        with st.expander(label):
            _render_review_sections(item, weekly=item["review_type"] == "weekly")


def render() -> None:
    st.title("AI复盘")
    st.info("AI 复盘仅用于纪律总结，不构成投资建议，不会自动交易。")

    settings = load_settings()

    st.subheader("日复盘")
    daily_date = st.date_input("复盘日期", value=date.today(), key="ai_daily_date")
    if st.button("生成 AI 日复盘", type="primary", key="generate_ai_daily"):
        with db_session() as conn:
            review, saved, message = generate_daily_ai_review(
                conn,
                settings,
                daily_date.strftime("%Y-%m-%d"),
            )
        if saved:
            st.success(message)
            st.session_state["latest_ai_daily_review"] = review
        else:
            st.warning(message)

    latest_daily = st.session_state.get("latest_ai_daily_review")
    if latest_daily:
        _render_review_sections(latest_daily, weekly=False)

    st.divider()

    st.subheader("周复盘")
    end_default = date.today()
    start_default = end_default - timedelta(days=6)
    c1, c2 = st.columns(2)
    with c1:
        week_start = st.date_input("周开始日期", value=start_default, key="ai_week_start")
    with c2:
        week_end = st.date_input("周结束日期", value=end_default, key="ai_week_end")

    if st.button("生成 AI 周复盘", type="primary", key="generate_ai_weekly"):
        with db_session() as conn:
            review, saved, message = generate_weekly_ai_review(
                conn,
                settings,
                week_start.strftime("%Y-%m-%d"),
                week_end.strftime("%Y-%m-%d"),
            )
        if saved:
            st.success(message)
            st.session_state["latest_ai_weekly_review"] = review
        else:
            st.warning(message)

    latest_weekly = st.session_state.get("latest_ai_weekly_review")
    if latest_weekly:
        _render_review_sections(latest_weekly, weekly=True)

    with get_connection() as conn:
        history_rows = get_latest_ai_reviews(conn, limit=20)
    if history_rows:
        _render_history(history_rows)
    else:
        st.info("暂无历史 AI 复盘")


render()
