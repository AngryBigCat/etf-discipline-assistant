from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskItem:
    task_date: str
    category: str
    task_type: str
    title: str
    description: str = ""
    priority: str = "normal"
    status: str = "pending"
    source_type: str | None = None
    source_key: str = ""
    due_date: str | None = None
    note: str | None = None

    def to_row(self) -> dict:
        return {
            "task_date": self.task_date,
            "category": self.category,
            "task_type": self.task_type,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "source_type": self.source_type,
            "source_key": self.source_key,
            "due_date": self.due_date,
            "note": self.note,
        }

    @property
    def unique_key(self) -> tuple[str, str | None, str]:
        return (self.task_type, self.source_type, self.source_key or "")
