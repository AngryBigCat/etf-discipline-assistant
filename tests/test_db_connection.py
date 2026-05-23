from __future__ import annotations

import sqlite3
from pathlib import Path

from src.db.connection import get_connection
from src.db.schema import _table_has_column


def test_get_connection_applies_ai_review_migration(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE ai_review (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_type TEXT NOT NULL,
            target_date TEXT NOT NULL DEFAULT '',
            week_start TEXT NOT NULL DEFAULT '',
            week_end TEXT NOT NULL DEFAULT '',
            source_type TEXT NOT NULL,
            source_digest TEXT,
            prompt_version TEXT NOT NULL DEFAULT 'v1',
            provider TEXT DEFAULT 'mock',
            model TEXT,
            input_snapshot TEXT,
            output_text TEXT,
            discipline_summary TEXT,
            risk_summary TEXT,
            action_suggestion TEXT,
            status TEXT DEFAULT 'success',
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(review_type, target_date, week_start, week_end, prompt_version)
        )
        """
    )
    conn.commit()
    conn.close()

    with get_connection(db_path) as migrated:
        assert _table_has_column(migrated, "ai_review", "behavior_findings")
