from __future__ import annotations

from datetime import datetime


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")
