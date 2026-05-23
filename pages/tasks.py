from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.config.settings import load_settings
from src.db.connection import db_session, get_connection
from src.tasks.actions import get_task_guidance, is_executable_task
from src.tasks.service import (
    complete_task,
    execute_task,
    filter_history_tasks,
    get_recent_task_history,
    get_task_dashboard,
    refresh_tasks_for_date,
    skip_task,
    split_tasks_for_display,
)
from src.ui.labels import (
    localize_task_category,
    localize_task_priority_badge,
    localize_task_source_type,
    localize_task_status_badge,
    localize_task_type,
)


def _split_task_sections(tasks: list[dict]) -> tuple[list[dict], list[dict]]:
    split = split_tasks_for_display(tasks)
    return split["today_tasks"], split["risk_tasks"]


def _task_to_display_row(task: dict) -> dict:
    return {
        "priority": localize_task_priority_badge(task.get("priority")),
        "title": task.get("title") or "—",
        "description": task.get("description") or "—",
        "category": localize_task_category(task.get("category")),
        "task_type": localize_task_type(task.get("task_type")),
        "source_type": localize_task_source_type(task.get("source_type")),
        "status": localize_task_status_badge(task.get("status")),
        "note": task.get("note") or "—",
    }


def _render_task_table(tasks: list[dict], *, empty_message: str) -> None:
    if not tasks:
        st.info(empty_message)
        return
    display_df = pd.DataFrame([_task_to_display_row(task) for task in tasks])
    column_map = {
        "priority": "优先级",
        "title": "标题",
        "description": "描述",
        "category": "任务分类",
        "task_type": "任务类型",
        "source_type": "来源",
        "status": "状态",
        "note": "备注",
    }
    st.dataframe(display_df.rename(columns=column_map), use_container_width=True, hide_index=True)


def _render_task_cards(
    tasks: list[dict],
    *,
    settings: dict,
    key_prefix: str,
    empty_message: str,
    highlight_high_priority: bool = False,
) -> None:
    if not tasks:
        st.info(empty_message)
        return

    for task in tasks:
        task_id = int(task["id"])
        task_type = str(task.get("task_type") or "")
        label = (
            f"{localize_task_priority_badge(task.get('priority'))} · "
            f"{localize_task_status_badge(task.get('status'))} · "
            f"{task.get('title')}"
        )
        expanded = highlight_high_priority and task.get("priority") == "high"
        with st.expander(label, expanded=expanded):
            st.markdown(task.get("description") or "—")
            meta1, meta2, meta3 = st.columns(3)
            with meta1:
                st.caption(f"任务分类：{localize_task_category(task.get('category'))}")
            with meta2:
                st.caption(f"任务类型：{localize_task_type(task.get('task_type'))}")
            with meta3:
                st.caption(f"来源：{localize_task_source_type(task.get('source_type'))}")

            if is_executable_task(task_type):
                st.caption("该任务支持在任务中心一键执行。")
            else:
                guidance = get_task_guidance(task_type) or "该任务需人工处理，不支持一键执行。"
                st.info(f"前往处理说明：{guidance}")

            note = st.text_input("备注", key=f"{key_prefix}_note_{task_id}")

            if is_executable_task(task_type):
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("执行任务", key=f"{key_prefix}_exec_{task_id}", type="primary"):
                        with st.spinner("正在执行任务..."):
                            with db_session() as conn:
                                result = execute_task(conn, settings, task_id)
                        if result.success:
                            st.success("任务执行成功，已刷新任务列表。")
                        else:
                            st.error(f"任务执行失败：{result.message}")
                            if result.detail:
                                st.caption(result.detail)
                        st.rerun()
                with col2:
                    if st.button("标记完成", key=f"{key_prefix}_done_{task_id}"):
                        with db_session() as conn:
                            complete_task(conn, task_id, note=note or None)
                        st.rerun()
                with col3:
                    if st.button("跳过任务", key=f"{key_prefix}_skip_{task_id}"):
                        with db_session() as conn:
                            skip_task(conn, task_id, note=note or None)
                        st.rerun()
            else:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("标记完成", key=f"{key_prefix}_done_{task_id}"):
                        with db_session() as conn:
                            complete_task(conn, task_id, note=note or None)
                        st.rerun()
                with col2:
                    if st.button("跳过任务", key=f"{key_prefix}_skip_{task_id}"):
                        with db_session() as conn:
                            skip_task(conn, task_id, note=note or None)
                        st.rerun()


def render() -> None:
    st.title("任务中心")
    st.info(
        "任务中心仅用于投资流程提醒，不构成投资建议，不会自动交易。"
        "支持一键执行数据更新、信号生成、报告生成等安全任务；"
        "涉及持仓、交易和审核的任务仍需人工处理。"
    )

    settings = load_settings()
    task_date = st.date_input("任务日期", value=date.today())

    if st.button("刷新今日任务", type="primary"):
        with db_session() as conn:
            refresh_tasks_for_date(conn, settings, task_date.strftime("%Y-%m-%d"))
        st.success("任务已刷新")
        st.rerun()

    task_date_str = task_date.strftime("%Y-%m-%d")
    with get_connection() as conn:
        dashboard = get_task_dashboard(conn, settings, task_date_str)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("待处理", dashboard["pending_count"])
    with c2:
        st.metric("已完成", dashboard["done_count"])
    with c3:
        st.metric("已跳过", dashboard["skipped_count"])
    with c4:
        st.metric("高优先级", dashboard["high_priority_count"])

    today_tasks, risk_tasks = _split_task_sections(dashboard.get("tasks") or [])

    st.subheader("今日任务")
    _render_task_cards(
        today_tasks,
        settings=settings,
        key_prefix=f"today_{task_date_str}",
        empty_message="今日暂无待处理任务，可点击「刷新今日任务」生成。",
    )

    st.subheader("风险任务")
    _render_task_cards(
        risk_tasks,
        settings=settings,
        key_prefix=f"risk_{task_date_str}",
        empty_message="当前没有待处理的风险任务。",
        highlight_high_priority=True,
    )

    st.subheader("历史任务")
    st.caption("历史任务仅展示已完成或已跳过的记录，待处理任务请在上方查看。")
    status_filter = st.selectbox(
        "状态筛选",
        options=["all", "done", "skipped"],
        format_func=lambda value: {
            "all": "全部",
            "done": "已完成",
            "skipped": "已跳过",
        }[value],
    )
    with get_connection() as conn:
        history_rows = filter_history_tasks(get_recent_task_history(conn, limit=100), status_filter)

    history_df = pd.DataFrame(
        [
            {
                "task_date": row.get("task_date"),
                "priority": localize_task_priority_badge(row.get("priority")),
                "title": row.get("title"),
                "category": localize_task_category(row.get("category")),
                "task_type": localize_task_type(row.get("task_type")),
                "source_type": localize_task_source_type(row.get("source_type")),
                "status": localize_task_status_badge(row.get("status")),
                "updated_at": row.get("updated_at") or "—",
            }
            for row in history_rows
        ]
    )
    if history_df.empty:
        st.info("暂无历史任务")
    else:
        column_map = {
            "task_date": "任务日期",
            "priority": "优先级",
            "title": "标题",
            "category": "任务分类",
            "task_type": "任务类型",
            "source_type": "来源",
            "status": "状态",
            "updated_at": "更新时间",
        }
        st.dataframe(history_df.rename(columns=column_map), use_container_width=True, hide_index=True)


render()
