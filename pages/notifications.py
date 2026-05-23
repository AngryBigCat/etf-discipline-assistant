from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db.connection import db_session, get_connection
from src.notifications.config import format_email_settings_display
from src.notifications.models import EVENT_TEST_EMAIL, LEVEL_INFO
from src.notifications.repository import list_notification_logs
from src.notifications.service import send_notification
from src.notifications.templates import build_test_email_body
from src.ui.labels import localize_notification_event_type, localize_notification_status


def main() -> None:
    st.title("通知中心")
    st.caption(
        "邮件通知只用于流程提醒和风险提示，不构成投资建议，不会自动交易。"
    )

    display = format_email_settings_display()
    st.subheader("邮件配置状态")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("邮件通知", value=display["enabled"], disabled=True)
        st.text_input("SMTP 主机", value=display["smtp_host"], disabled=True)
        st.text_input("SMTP 用户", value=display["smtp_username"], disabled=True)
        st.text_input("SMTP 密码", value=display["smtp_password"], disabled=True)
    with col2:
        st.text_input("发件人", value=display["email_from"], disabled=True)
        st.text_input("收件人", value=display["email_to"], disabled=True)
        st.text_input("定时任务失败提醒", value=display["notify_on_scheduler_failure"], disabled=True)
        st.text_input("高优先级任务提醒", value=display["notify_on_high_priority_tasks"], disabled=True)
        st.text_input("仓位风险提醒", value=display["notify_on_portfolio_risk"], disabled=True)

    st.info(
        "SMTP 密码、API Key 等敏感信息仅通过 `.env` 配置，"
        "本页面不会展示明文，也不会写入数据库。"
    )

    if st.button("发送测试邮件", type="primary", use_container_width=True):
        with db_session() as conn:
            result = send_notification(
                conn,
                event_type=EVENT_TEST_EMAIL,
                level=LEVEL_INFO,
                title="测试邮件",
                body=build_test_email_body(),
            )
        if result.status == "success":
            st.success(result.message)
        elif result.status == "skipped":
            st.warning(result.message)
        else:
            st.error(result.error or result.message)
        st.rerun()

    st.divider()
    st.subheader("通知日志")
    with get_connection() as conn:
        logs = list_notification_logs(conn, limit=100)

    if not logs:
        st.info("暂无通知日志。")
        return

    rows = []
    for row in logs:
        rows.append(
            {
                "created_at": row.get("created_at") or "—",
                "channel": row.get("channel") or "—",
                "event_type": localize_notification_event_type(row.get("event_type")),
                "level": row.get("level") or "—",
                "title": row.get("title") or "—",
                "recipient_masked": row.get("recipient_masked") or "—",
                "status": localize_notification_status(row.get("status")),
                "error_message": row.get("error_message") or "—",
            }
        )
    st.dataframe(
        pd.DataFrame(rows).rename(
            columns={
                "created_at": "时间",
                "channel": "渠道",
                "event_type": "事件类型",
                "level": "等级",
                "title": "标题",
                "recipient_masked": "收件人",
                "status": "状态",
                "error_message": "错误信息",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    main()
else:
    main()
