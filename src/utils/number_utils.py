from __future__ import annotations


def format_pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def format_number(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"
