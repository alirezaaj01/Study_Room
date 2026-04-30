"""
data/models.py
Pure Python dataclasses — no external dependencies.
All data structures shared across the project.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING  = "pending"
    DONE     = "done"
    ARCHIVED = "archived"


class TaskPriority(int, Enum):
    HIGH   = 1
    MEDIUM = 2
    LOW    = 3


class SessionType(str, Enum):
    WORK        = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK  = "long_break"


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Task:
    """Represents a single study task."""
    id:                 int
    title:              str
    description:        str              = ""
    tag:                str              = ""
    priority:           TaskPriority     = TaskPriority.MEDIUM
    status:             TaskStatus       = TaskStatus.PENDING
    created_at:         str              = field(default_factory=lambda: datetime.now().isoformat())
    due_date:           Optional[str]    = None
    pomodoros_done:     int              = 0
    pomodoros_planned:  int              = 1

    @property
    def is_done(self) -> bool:
        return self.status == TaskStatus.DONE

    @property
    def progress_text(self) -> str:
        return f"{self.pomodoros_done}/{self.pomodoros_planned}"


@dataclass
class Session:
    """Represents a single Pomodoro session recorded in the DB."""
    id:         int
    task_id:    Optional[int]
    start_time: str
    end_time:   Optional[str]
    duration:   int               # seconds
    type:       SessionType
    completed:  bool              = False
    notes:      str               = ""


@dataclass
class Workspace:
    """A saved workspace recipe launched at session start."""
    name:           str
    apps:           list[str]   = field(default_factory=list)   # executable paths
    files:          list[str]   = field(default_factory=list)   # file paths
    do_not_disturb: bool        = True

    def to_dict(self) -> dict:
        return {
            "name":            self.name,
            "apps":            self.apps,
            "files":           self.files,
            "do_not_disturb":  self.do_not_disturb,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Workspace":
        return cls(
            name=d.get("name", ""),
            apps=d.get("apps", []),
            files=d.get("files", []),
            do_not_disturb=d.get("do_not_disturb", True),
        )


@dataclass
class DailyStats:
    """Aggregated statistics for a single day."""
    date:           str
    work_seconds:   int
    sessions_count: int
    tasks:          list[str]   = field(default_factory=list)

    @property
    def work_hours(self) -> float:
        return round(self.work_seconds / 3600, 2)

    @property
    def work_minutes(self) -> int:
        return self.work_seconds // 60
