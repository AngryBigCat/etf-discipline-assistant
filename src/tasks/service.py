from __future__ import annotations

from typing import Any

from src.db.repository import (
    list_recent_tasks,
    list_tasks_by_date,
    mark_task_done,
    mark_task_skipped,
    upsert_task_item,
)
from src.tasks.generators import generate_all_tasks


def refresh_tasks_for_date(conn, settings: dict[str, Any], task_date: str) -> list[dict[str, Any]]:
    generated_tasks = generate_all_tasks(conn, settings, task_date)
    generated_keys = {task.unique_key for task in generated_tasks}

    for task in generated_tasks:
        upsert_task_item(conn, task.to_row())

    obsolete_rows = conn.execute(
        """
        SELECT id, task_type, source_type, source_key
        FROM task_item
        WHERE task_date = ? AND status = 'pending'
        """,
        (task_date,),
    ).fetchall()
    for row in obsolete_rows:
        key = (row["task_type"], row["source_type"], row["source_key"] or "")
        if key not in generated_keys:
            conn.execute("DELETE FROM task_item WHERE id = ?", (row["id"],))

    return [dict(row) for row in list_tasks_by_date(conn, task_date)]


def get_task_dashboard(conn, settings: dict[str, Any], task_date: str) -> dict[str, Any]:
    rows = list_tasks_by_date(conn, task_date)
    if not rows:
        rows = refresh_tasks_for_date(conn, settings, task_date)
        rows = list_tasks_by_date(conn, task_date)

    tasks = [dict(row) for row in rows]
    pending_count = sum(1 for task in tasks if task["status"] == "pending")
    done_count = sum(1 for task in tasks if task["status"] == "done")
    skipped_count = sum(1 for task in tasks if task["status"] == "skipped")
    high_priority_count = sum(
        1 for task in tasks if task["status"] == "pending" and task["priority"] == "high"
    )
    return {
        "task_date": task_date,
        "pending_count": pending_count,
        "done_count": done_count,
        "skipped_count": skipped_count,
        "high_priority_count": high_priority_count,
        "tasks": tasks,
    }


def complete_task(conn, task_id: int, note: str | None = None) -> None:
    mark_task_done(conn, task_id, note=note)


def skip_task(conn, task_id: int, note: str | None = None) -> None:
    mark_task_skipped(conn, task_id, note=note)


def get_recent_task_history(conn, limit: int = 100) -> list[dict[str, Any]]:
    return [dict(row) for row in list_recent_tasks(conn, limit=limit)]
