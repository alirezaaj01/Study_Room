"""
core/session_tracker.py
Records Pomodoro sessions to SQLite and provides analytics queries.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional

from data.database import DatabaseManager
from data.models import DailyStats, Session, SessionType

logger = logging.getLogger(__name__)


class SessionTracker:
    """Records sessions and provides aggregated statistics."""

    def __init__(self) -> None:
        self._db = DatabaseManager.instance()
        self._active_session_id: Optional[int] = None

    # ── Session lifecycle ─────────────────────────────────────────────────────

    def start_session(
        self,
        session_type: SessionType,
        task_id: Optional[int] = None,
    ) -> int:
        """
        Insert a new session row with end_time=NULL.
        Returns the new session id.
        """
        now = datetime.now().isoformat()
        cur = self._db.execute(
            """
            INSERT INTO sessions (task_id, start_time, type, completed)
            VALUES (?, ?, ?, 0)
            """,
            (task_id, now, session_type.value),
        )
        self._active_session_id = cur.lastrowid
        logger.info("Session started id=%d type=%s", self._active_session_id, session_type.value)
        return self._active_session_id

    def end_session(
        self,
        session_id: int,
        duration_seconds: int,
        completed: bool = True,
        notes: str = "",
    ) -> None:
        """Fill in end_time, duration, completed for an existing session row."""
        now = datetime.now().isoformat()
        self._db.execute(
            """
            UPDATE sessions
            SET end_time = ?, duration = ?, completed = ?, notes = ?
            WHERE id = ?
            """,
            (now, duration_seconds, int(completed), notes, session_id),
        )
        if self._active_session_id == session_id:
            self._active_session_id = None
        logger.info("Session ended id=%d duration=%ds completed=%s", session_id, duration_seconds, completed)

    def end_active_session(self, duration_seconds: int, completed: bool = True) -> None:
        """Convenience: end whatever session is currently active."""
        if self._active_session_id is not None:
            self.end_session(self._active_session_id, duration_seconds, completed)

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_daily_stats(self, date: Optional[str] = None) -> DailyStats:
        """
        Return aggregated stats for a specific date (YYYY-MM-DD).
        Defaults to today.
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        rows = self._db.fetchall(
            """
            SELECT s.duration, s.type, t.tag
            FROM sessions s
            LEFT JOIN tasks t ON s.task_id = t.id
            WHERE s.type = 'work'
              AND s.completed = 1
              AND date(s.start_time) = ?
            """,
            (date,),
        )
        work_seconds = sum(r["duration"] for r in rows)
        tags = list({r["tag"] for r in rows if r["tag"]})
        return DailyStats(
            date=date,
            work_seconds=work_seconds,
            sessions_count=len(rows),
            tasks=tags,
        )

    def get_weekly_stats(self, start_date: Optional[str] = None) -> list[DailyStats]:
        """
        Return a list of DailyStats for 7 days starting from start_date.
        Defaults to the beginning of the current week (Monday).
        """
        if start_date is None:
            today = datetime.now()
            start_dt = today - timedelta(days=today.weekday())
            start_date = start_dt.strftime("%Y-%m-%d")
        result = []
        for i in range(7):
            d = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=i)).strftime("%Y-%m-%d")
            result.append(self.get_daily_stats(d))
        return result

    def get_last_n_days(self, n: int = 7) -> list[DailyStats]:
        """Return stats for the last N days (most recent last)."""
        today = datetime.now()
        result = []
        for i in range(n - 1, -1, -1):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            result.append(self.get_daily_stats(d))
        return result

    def get_heatmap_data(self, weeks: int = 12) -> dict[str, int]:
        """
        Return {date_str: work_seconds} for the past `weeks` weeks.
        Suitable for rendering a GitHub-style contribution heatmap.
        """
        cutoff = (datetime.now() - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
        rows = self._db.fetchall(
            """
            SELECT date(start_time) AS day, SUM(duration) AS total
            FROM sessions
            WHERE type = 'work' AND completed = 1 AND date(start_time) >= ?
            GROUP BY day
            """,
            (cutoff,),
        )
        return {r["day"]: r["total"] for r in rows}

    def get_total_today(self) -> int:
        """Return total work seconds completed today."""
        today = datetime.now().strftime("%Y-%m-%d")
        row = self._db.fetchone(
            """
            SELECT COALESCE(SUM(duration), 0) AS total
            FROM sessions
            WHERE type = 'work' AND completed = 1 AND date(start_time) = ?
            """,
            (today,),
        )
        return row["total"] if row else 0

    def get_streak(self) -> int:
        """Return the current consecutive study-day streak."""
        rows = self._db.fetchall(
            """
            SELECT DISTINCT date(start_time) AS day
            FROM sessions
            WHERE type = 'work' AND completed = 1
            ORDER BY day DESC
            """
        )
        if not rows:
            return 0
        streak = 0
        today = datetime.now().date()
        for i, row in enumerate(rows):
            expected = today - timedelta(days=i)
            if datetime.strptime(row["day"], "%Y-%m-%d").date() == expected:
                streak += 1
            else:
                break
        return streak
