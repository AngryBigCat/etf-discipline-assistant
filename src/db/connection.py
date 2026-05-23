from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.config.settings import get_database_path


def ensure_database_dir(db_path: Path | None = None) -> Path:
    path = db_path or get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = ensure_database_dir(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
