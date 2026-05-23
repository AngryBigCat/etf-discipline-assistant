from __future__ import annotations

import sqlite3
from typing import Any

from src.scheduler.defaults import DEFAULT_SCHEDULER_JOBS


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def ensure_default_scheduler_jobs(conn: sqlite3.Connection) -> None:
    for job in DEFAULT_SCHEDULER_JOBS:
        conn.execute(
            """
            INSERT OR IGNORE INTO scheduler_job_config (
                job_key, name, description, enabled, cron_expr, timezone,
                job_type, params_json, max_instances, coalesce, misfire_grace_time
            ) VALUES (
                :job_key, :name, :description, :enabled, :cron_expr, :timezone,
                :job_type, :params_json, :max_instances, :coalesce, :misfire_grace_time
            )
            """,
            job,
        )


def list_scheduler_jobs(
    conn: sqlite3.Connection,
    *,
    enabled_only: bool = False,
) -> list[dict[str, Any]]:
    where_clause = "WHERE j.enabled = 1" if enabled_only else ""
    cur = conn.execute(
        f"""
        SELECT
            j.*,
            (
                SELECT status
                FROM scheduler_run_log
                WHERE job_key = j.job_key
                ORDER BY id DESC
                LIMIT 1
            ) AS last_run_status,
            (
                SELECT started_at
                FROM scheduler_run_log
                WHERE job_key = j.job_key
                ORDER BY id DESC
                LIMIT 1
            ) AS last_run_started_at,
            (
                SELECT finished_at
                FROM scheduler_run_log
                WHERE job_key = j.job_key
                ORDER BY id DESC
                LIMIT 1
            ) AS last_run_finished_at
        FROM scheduler_job_config j
        {where_clause}
        ORDER BY j.id
        """
    )
    return [dict(row) for row in cur.fetchall()]


def get_scheduler_job(conn: sqlite3.Connection, job_key: str) -> dict[str, Any] | None:
    cur = conn.execute(
        "SELECT * FROM scheduler_job_config WHERE job_key = ?",
        (job_key,),
    )
    return _row_to_dict(cur.fetchone())


def upsert_scheduler_job(conn: sqlite3.Connection, job: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO scheduler_job_config (
            job_key, name, description, enabled, cron_expr, timezone,
            job_type, params_json, max_instances, coalesce, misfire_grace_time
        ) VALUES (
            :job_key, :name, :description, :enabled, :cron_expr, :timezone,
            :job_type, :params_json, :max_instances, :coalesce, :misfire_grace_time
        )
        ON CONFLICT(job_key) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            enabled = excluded.enabled,
            cron_expr = excluded.cron_expr,
            timezone = excluded.timezone,
            job_type = excluded.job_type,
            params_json = excluded.params_json,
            max_instances = excluded.max_instances,
            coalesce = excluded.coalesce,
            misfire_grace_time = excluded.misfire_grace_time,
            updated_at = CURRENT_TIMESTAMP
        """,
        job,
    )


def update_scheduler_job_enabled(
    conn: sqlite3.Connection,
    job_key: str,
    enabled: bool,
) -> None:
    conn.execute(
        """
        UPDATE scheduler_job_config
        SET enabled = ?, updated_at = CURRENT_TIMESTAMP
        WHERE job_key = ?
        """,
        (1 if enabled else 0, job_key),
    )


def save_scheduler_run_log(conn: sqlite3.Connection, row: dict[str, Any]) -> int:
    cur = conn.execute(
        """
        INSERT INTO scheduler_run_log (
            job_key, scheduled_time, started_at, finished_at, status, message, detail
        ) VALUES (
            :job_key, :scheduled_time, :started_at, :finished_at, :status, :message, :detail
        )
        """,
        row,
    )
    return int(cur.lastrowid)


def update_scheduler_run_log(
    conn: sqlite3.Connection,
    log_id: int,
    fields: dict[str, Any],
) -> None:
    allowed = {"scheduled_time", "started_at", "finished_at", "status", "message", "detail"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{key} = :{key}" for key in updates)
    conn.execute(
        f"UPDATE scheduler_run_log SET {set_clause} WHERE id = :log_id",
        {**updates, "log_id": log_id},
    )


def list_scheduler_run_logs(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT
            l.*,
            j.name AS job_name
        FROM scheduler_run_log l
        LEFT JOIN scheduler_job_config j ON j.job_key = l.job_key
        ORDER BY l.started_at DESC, l.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]
