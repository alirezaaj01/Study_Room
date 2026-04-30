"""
core/task_manager.py
CRUD layer for the tasks table.  No UI dependencies.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional

from data.database import DatabaseManager
from data.models import Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)


class TaskManager:
    """All task CRUD operations backed by SQLite."""

    def __init__(self) -> None:
        self._db = DatabaseManager.instance()

    # ── Create ────────────────────────────────────────────────────────────────

    def create_task(
        self,
        title: str,
        description: str = "",
        tag: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[str] = None,
        pomodoros_planned: int = 1,
    ) -> Task:
        """Insert a new task and return the created Task object."""
        now = datetime.now().isoformat()
        cur = self._db.execute(
            """
            INSERT INTO tasks
                (title, description, tag, priority, status, created_at, due_date, pomodoros_planned)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (title, description, tag, priority.value, now, due_date, pomodoros_planned),
        )
        task_id = cur.lastrowid
        logger.info("Created task id=%d title=%r", task_id, title)
        return self.get_task(task_id)

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_task(self, task_id: int) -> Task:
        row = self._db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if row is None:
            raise ValueError(f"Task {task_id} not found.")
        return self._row_to_task(row)

    def get_tasks(
        self,
        status: Optional[TaskStatus] = TaskStatus.PENDING,
        tag: Optional[str] = None,
    ) -> list[Task]:
        """Return tasks filtered by status and/or tag, ordered by priority."""
        sql = "SELECT * FROM tasks WHERE 1=1"
        params: list = []
        if status is not None:
            sql += " AND status = ?"
            params.append(status.value)
        if tag:
            sql += " AND tag = ?"
            params.append(tag)
        sql += " ORDER BY priority ASC, created_at DESC"
        rows = self._db.fetchall(sql, tuple(params))
        return [self._row_to_task(r) for r in rows]

    def get_all_tasks(self) -> list[Task]:
        return self.get_tasks(status=None)

    def get_tags(self) -> list[str]:
        """Return distinct non-empty tags sorted alphabetically."""
        rows = self._db.fetchall(
            "SELECT DISTINCT tag FROM tasks WHERE tag != '' ORDER BY tag"
        )
        return [r["tag"] for r in rows]

    # ── Update ────────────────────────────────────────────────────────────────

    def update_task(self, task_id: int, **kwargs) -> bool:
        """
        Update arbitrary task fields.
        Allowed keys: title, description, tag, priority, due_date,
                      pomodoros_planned, status.
        """
        allowed = {
            "title", "description", "tag", "priority",
            "due_date", "pomodoros_planned", "status",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        # Serialize enums
        if "priority" in updates and isinstance(updates["priority"], TaskPriority):
            updates["priority"] = updates["priority"].value
        if "status" in updates and isinstance(updates["status"], TaskStatus):
            updates["status"] = updates["status"].value

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]
        self._db.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", tuple(values))
        logger.debug("Updated task id=%d fields=%s", task_id, list(updates.keys()))
        return True

    def mark_done(self, task_id: int) -> bool:
        self._db.execute(
            "UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,)
        )
        logger.info("Task id=%d marked done.", task_id)
        return True

    def mark_pending(self, task_id: int) -> bool:
        self._db.execute(
            "UPDATE tasks SET status = 'pending' WHERE id = ?", (task_id,)
        )
        return True

    def archive_task(self, task_id: int) -> bool:
        self._db.execute(
            "UPDATE tasks SET status = 'archived' WHERE id = ?", (task_id,)
        )
        return True

    def increment_pomodoro(self, task_id: int) -> int:
        """Increment pomodoros_done by 1 and return the new count."""
        self._db.execute(
            "UPDATE tasks SET pomodoros_done = pomodoros_done + 1 WHERE id = ?",
            (task_id,),
        )
        row = self._db.fetchone(
            "SELECT pomodoros_done FROM tasks WHERE id = ?", (task_id,)
        )
        count = row["pomodoros_done"] if row else 0
        logger.debug("Task id=%d pomodoros_done=%d", task_id, count)
        return count

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_task(self, task_id: int) -> bool:
        self._db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        logger.info("Deleted task id=%d", task_id)
        return True

    # ── Helper ────────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_task(row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            tag=row["tag"] or "",
            priority=TaskPriority(row["priority"]),
            status=TaskStatus(row["status"]),
            created_at=row["created_at"],
            due_date=row["due_date"],
            pomodoros_done=row["pomodoros_done"],
            pomodoros_planned=row["pomodoros_planned"],
        )
