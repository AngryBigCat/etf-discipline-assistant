from __future__ import annotations

import re
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.config.settings import load_settings
from src.db.connection import db_session, get_connection
from src.db.repository import list_daily_reports, list_weekly_reports
from src.reports.daily_report import build_and_save_daily_report
from src.reports.weekly_report import build_and_save_weekly_report
from src.ui.labels import rename_columns

_SECTION_HEADER_RE = re.compile(r"^### .+\n+", re.MULTILINE)


def _strip_section_headers(text: str | None) -> str:
    if not text:
        return "—"
    cleaned = _SECTION_HEADER_RE.sub("", text).strip()
    return cleaned or "—"


def _preview(text: str | None, max_len: int = 120) -> str:
    if not text:
        return "—"
    plain = _strip_section_headers(text).replace("\n", " ").strip()
    if len(plain) <= max_len:
        return plain
    return plain[:max_len] + "…"


def _render_daily_sections(report: dict[str, str | None]) -> None:
    st.markdown("#### 概况")
    st.markdown(_strip_section_headers(report.get("summary")))
    st.markdown("#### 风险提示")
    st.markdown(_strip_section_headers(report.get("risk_warning")))
    st.markdown("#### 操作建议")
    st.markdown(_strip_section_headers(report.get("action_suggestion")))


def _render_weekly_sections(report: dict[str, str | None]) -> None:
    st.markdown("#### 概况")
    st.markdown(_strip_section_headers(report.get("summary")))
    st.markdown("#### 纪律统计")
    st.markdown(_strip_section_headers(report.get("discipline_summary")))
    st.markdown("#### 风险摘要")
    st.markdown(_strip_section_headers(report.get("risk_summary")))
    st.markdown("#### 操作建议")
    st.markdown(_strip_section_headers(report.get("action_suggestion")))


def _render_daily_history(rows: list) -> None:
    st.markdown("#### 历史日报")
    preview_df = pd.DataFrame(
        [
            {
                "report_date": row["report_date"],
                "preview": _preview(row["summary"], max_len=80),
            }
            for row in rows
        ]
    )
    st.dataframe(
        rename_columns(preview_df),
        use_container_width=True,
        hide_index=True,
    )
    for row in rows:
        label = f"{row['report_date']} · {_preview(row['summary'], max_len=60)}"
        with st.expander(label):
            _render_daily_sections(dict(row))


def _render_weekly_history(rows: list) -> None:
    st.markdown("#### 历史周报")
    preview_df = pd.DataFrame(
        [
            {
                "week_start": row["week_start"],
                "week_end": row["week_end"],
                "preview": _preview(row["summary"], max_len=80),
            }
            for row in rows
        ]
    )
    st.dataframe(
        rename_columns(preview_df),
        use_container_width=True,
        hide_index=True,
    )
    for row in rows:
        label = (
            f"{row['week_start']} ~ {row['week_end']} · "
            f"{_preview(row['summary'], max_len=50)}"
        )
        with st.expander(label):
            _render_weekly_sections(dict(row))


def render() -> None:
    st.title("报告复盘")
    st.caption("基于账户快照、策略信号与交易日志生成模板化日报/周报，用于复盘投资纪律")

    settings = load_settings()

    st.subheader("日报")
    daily_date = st.date_input("报告日期", value=date.today(), key="daily_report_date")
    if st.button("生成今日日报", type="primary", key="generate_daily"):
        with db_session() as conn:
            report, saved, message = build_and_save_daily_report(
                conn,
                settings,
                daily_date.strftime("%Y-%m-%d"),
            )
        if saved:
            st.success(message)
            st.session_state["latest_daily_report"] = report
        else:
            st.warning(message)

    latest_daily = st.session_state.get("latest_daily_report")
    if latest_daily:
        _render_daily_sections(latest_daily)

    with get_connection() as conn:
        daily_rows = list_daily_reports(conn, limit=30)
    if daily_rows:
        _render_daily_history(daily_rows)
    else:
        st.info("暂无历史日报")

    st.divider()

    st.subheader("周报")
    end_default = date.today()
    start_default = end_default - timedelta(days=6)
    c1, c2 = st.columns(2)
    with c1:
        week_start = st.date_input("周开始日期", value=start_default, key="week_start")
    with c2:
        week_end = st.date_input("周结束日期", value=end_default, key="week_end")

    if st.button("生成本周周报", type="primary", key="generate_weekly"):
        with db_session() as conn:
            report, saved, message = build_and_save_weekly_report(
                conn,
                settings,
                week_start.strftime("%Y-%m-%d"),
                week_end.strftime("%Y-%m-%d"),
            )
        if saved:
            st.success(message)
            st.session_state["latest_weekly_report"] = report
        else:
            st.warning(message)

    latest_weekly = st.session_state.get("latest_weekly_report")
    if latest_weekly:
        _render_weekly_sections(latest_weekly)

    with get_connection() as conn:
        weekly_rows = list_weekly_reports(conn, limit=20)
    if weekly_rows:
        _render_weekly_history(weekly_rows)
    else:
        st.info("暂无历史周报")


render()
