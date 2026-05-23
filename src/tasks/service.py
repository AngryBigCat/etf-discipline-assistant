from __future__ import annotations

from typing import Any

from src.db.repository import (
    get_task_item,
    list_recent_tasks,
    list_tasks_by_date,
    mark_task_done,
    mark_task_skipped,
    save_task_action_log,
    upsert_task_item,
)
from src.tasks.actions import TaskActionResult, execute_task_action
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
        refresh_tasks_for_date(conn, settings, task_date)
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


def execute_task(conn, settings: dict[str, Any], task_id: int) -> TaskActionResult:
    task_row = get_task_item(conn, task_id)
    if task_row is None:
        return TaskActionResult(success=False, message="任务不存在", should_mark_done=False)

    task = dict(task_row)
    result = execute_task_action(conn, settings, task)
    save_task_action_log(
        conn,
        {
            "task_id": task_id,
            "task_date": task.get("task_date"),
            "task_type": task.get("task_type"),
            "action_name": task.get("task_type"),
            "success": 1 if result.success else 0,
            "message": result.message,
            "detail": result.detail,
        },
    )

    if result.success and result.should_mark_done:
        mark_task_done(conn, task_id)

    refresh_tasks_for_date(conn, settings, str(task["task_date"]))
    return result


def get_recent_task_history(conn, limit: int = 100) -> list[dict[str, Any]]:
    return [dict(row) for row in list_recent_tasks(conn, limit=limit)]


def split_tasks_for_display(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    pending_tasks = [task for task in tasks if task.get("status") == "pending"]
    today_tasks = [task for task in pending_tasks if task.get("category") != "risk"]
    risk_tasks = [task for task in pending_tasks if task.get("category") == "risk"]
    risk_tasks.sort(
        key=lambda item: (0 if item.get("priority") == "high" else 1, item.get("id") or 0)
    )
    return {
        "pending_tasks": pending_tasks,
        "today_tasks": today_tasks,
        "risk_tasks": risk_tasks,
    }


def filter_history_tasks(
    rows: list[dict[str, Any]],
    status: str = "all",
) -> list[dict[str, Any]]:
    history = [row for row in rows if row.get("status") != "pending"]
    if status != "all":
        history = [row for row in history if row.get("status") == status]
    return history
