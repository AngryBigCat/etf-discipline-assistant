from __future__ import annotations

import sqlite3
from typing import Any


def _truncate_preview(body: str, limit: int = 500) -> str:
    text = body.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def save_notification_log(conn: sqlite3.Connection, row: dict[str, Any]) -> int:
    payload = dict(row)
    if payload.get("body_preview") is not None:
        payload["body_preview"] = _truncate_preview(str(payload["body_preview"]))
    cur = conn.execute(
        """
        INSERT INTO notification_log (
            channel, event_type, level, title, body_preview, recipient_masked,
            status, dedupe_key, source_type, source_key, error_message, sent_at
        ) VALUES (
            :channel, :event_type, :level, :title, :body_preview, :recipient_masked,
            :status, :dedupe_key, :source_type, :source_key, :error_message, :sent_at
        )
        """,
        payload,
    )
    return int(cur.lastrowid)


def list_notification_logs(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT *
        FROM notification_log
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]


def has_success_notification(
    conn: sqlite3.Connection,
    dedupe_key: str | None,
    *,
    channel: str = "email",
) -> bool:
    if not dedupe_key:
        return False
    cur = conn.execute(
        """
        SELECT 1
        FROM notification_log
        WHERE dedupe_key = ? AND channel = ? AND status = 'success'
        LIMIT 1
        """,
        (dedupe_key, channel),
    )
    return cur.fetchone() is not None
