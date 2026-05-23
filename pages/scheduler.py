from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db.connection import db_session, get_connection
from src.scheduler.repository import (
    ensure_default_scheduler_jobs,
    list_scheduler_jobs,
    list_scheduler_run_logs,
    update_scheduler_job_enabled,
)
from src.scheduler.runner import run_scheduler_job
from src.ui.labels import (
    localize_scheduler_job_type,
    localize_scheduler_status,
)


def _job_to_display_row(job: dict) -> dict:
    enabled = bool(job.get("enabled"))
    return {
        "name": job.get("name") or "—",
        "job_key": job.get("job_key") or "—",
        "enabled": "启用" if enabled else "停用",
        "cron_expr": job.get("cron_expr") or "—",
        "timezone": job.get("timezone") or "—",
        "job_type": localize_scheduler_job_type(job.get("job_type")),
        "last_run_status": localize_scheduler_status(job.get("last_run_status")),
        "last_run_started_at": job.get("last_run_started_at") or "—",
    }


def _log_to_display_row(row: dict) -> dict:
    return {
        "job_name": row.get("job_name") or row.get("job_key") or "—",
        "started_at": row.get("started_at") or "—",
        "finished_at": row.get("finished_at") or "—",
        "status": localize_scheduler_status(row.get("status")),
        "message": row.get("message") or "—",
        "detail": row.get("detail") or "—",
    }


def _render_job_actions(job: dict) -> None:
    job_key = str(job["job_key"])
    enabled = bool(job.get("enabled"))
    col1, col2, col3 = st.columns(3)
    with col1:
        if enabled:
            if st.button("停用", key=f"disable_{job_key}", use_container_width=True):
                with db_session() as conn:
                    update_scheduler_job_enabled(conn, job_key, False)
                st.success(f"{job_key} 已停用。")
                st.rerun()
        else:
            if st.button("启用", key=f"enable_{job_key}", use_container_width=True):
                with db_session() as conn:
                    update_scheduler_job_enabled(conn, job_key, True)
                st.success(f"{job_key} 已启用。")
                st.rerun()
    with col2:
        if st.button("立即执行", key=f"run_{job_key}", use_container_width=True):
            with st.spinner(f"正在执行 {job_key}..."):
                result = run_scheduler_job(job_key)
            if result.success:
                st.success(result.message)
                if result.detail and result.detail not in {"skipped"}:
                    st.code(result.detail)
            else:
                st.error(result.message)
                if result.detail:
                    st.code(result.detail)
            st.rerun()


def main() -> None:
    st.title("定时任务")
    st.caption(
        "定时任务只执行数据更新、信号生成、报告生成等安全流程，"
        "不会自动交易，不会自动修改真实持仓，不会自动审核策略信号。"
    )

    with get_connection() as conn:
        ensure_default_scheduler_jobs(conn)
        conn.commit()
        jobs = list_scheduler_jobs(conn)
        logs = list_scheduler_run_logs(conn, limit=100)

    st.subheader("定时任务列表")
    if not jobs:
        st.info("暂无定时任务配置。")
    else:
        display_df = pd.DataFrame([_job_to_display_row(job) for job in jobs])
        st.dataframe(
            display_df.rename(
                columns={
                    "name": "任务名称",
                    "job_key": "任务标识",
                    "enabled": "是否启用",
                    "cron_expr": "Cron 表达式",
                    "timezone": "时区",
                    "job_type": "任务类型",
                    "last_run_status": "最近运行状态",
                    "last_run_started_at": "最近运行时间",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        for job in jobs:
            with st.expander(f"{job.get('name')} · {job.get('job_key')}", expanded=False):
                st.markdown(job.get("description") or "—")
                _render_job_actions(job)

    st.divider()
    st.subheader("运行日志")
    if not logs:
        st.info("暂无运行日志。")
    else:
        log_df = pd.DataFrame([_log_to_display_row(row) for row in logs])
        st.dataframe(
            log_df.rename(
                columns={
                    "job_name": "任务名称",
                    "started_at": "开始时间",
                    "finished_at": "结束时间",
                    "status": "状态",
                    "message": "消息",
                    "detail": "详情",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()
else:
    main()
