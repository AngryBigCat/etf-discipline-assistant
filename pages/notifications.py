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
    readonly_fields = [
        ("邮件通知", display["enabled"]),
        ("SMTP 主机", display["smtp_host"]),
        ("SMTP 用户", display["smtp_username"]),
        ("SMTP 密码", display["smtp_password"]),
        ("发件人", display["email_from"]),
        ("收件人", display["email_to"]),
        ("定时任务失败提醒", display["notify_on_scheduler_failure"]),
        ("高优先级任务提醒", display["notify_on_high_priority_tasks"]),
        ("仓位风险提醒", display["notify_on_portfolio_risk"]),
    ]
    for index, (label, value) in enumerate(readonly_fields):
        target = col1 if index % 2 == 0 else col2
        with target:
            st.text_input(label, value=value, disabled=True, key=f"notify_status_{index}_{value}")

    st.info(
        "SMTP 密码、API Key 等敏感信息仅通过 `.env` 配置，"
        "本页面不会展示明文，也不会写入数据库。"
        "修改 `.env` 后刷新本页即可读取最新配置。"
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
