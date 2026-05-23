from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from src.config.settings import load_settings
from src.db.connection import db_session, ensure_database_dir, get_database_path
from src.tasks.service import refresh_tasks_for_date
from src.ui.labels import localize_task_priority, localize_task_type
from src.utils.date_utils import today_str


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate discipline task checklist")
    parser.add_argument("--date", dest="task_date", default=None, help="Task date YYYY-MM-DD")
    args = parser.parse_args()

    settings = load_settings()
    task_date = args.task_date or today_str()
    db_path = ensure_database_dir(get_database_path())

    with db_session(db_path) as conn:
        tasks = refresh_tasks_for_date(conn, settings, task_date)

    high_priority = [task for task in tasks if task.get("priority") == "high" and task.get("status") == "pending"]
    pending_count = sum(1 for task in tasks if task.get("status") == "pending")

    logger.info("任务日期：{}", task_date)
    logger.info("共生成/刷新 {} 条任务，其中待处理 {} 条", len(tasks), pending_count)
    logger.info("高优先级待处理 {} 条", len(high_priority))
    for task in high_priority[:10]:
        logger.info(
            "[{}] {} - {}",
            localize_task_priority(task.get("priority")),
            localize_task_type(task.get("task_type")),
            task.get("title"),
        )


if __name__ == "__main__":
    main()
