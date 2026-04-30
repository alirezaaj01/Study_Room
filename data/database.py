"""
data/database.py
Singleton SQLite manager.  All table creation and raw SQL lives here.
Higher-level logic belongs in core/ managers.
"""

from __future__ import annotations
import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

class DatabaseManager:
    """
    Singleton SQLite connection manager.
    Call DatabaseManager.instance() to get the shared instance.
    """

    _instance: Optional["DatabaseManager"] = None

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        logger.info("Database opened at %s", self._db_path)

    # ── Singleton access ──────────────────────────────────────────────────────

    @classmethod
    def instance(cls) -> "DatabaseManager":
        if cls._instance is None:
            raise RuntimeError("DatabaseManager not initialised. Call DatabaseManager.init() first.")
        return cls._instance

    @classmethod
    def init(cls, db_path: Path) -> "DatabaseManager":
        """Create (or reuse) the singleton."""
        if cls._instance is None:
            cls._instance = cls(db_path)
            cls._instance.initialize_db()
        return cls._instance

    # ── Schema ────────────────────────────────────────────────────────────────

    def initialize_db(self) -> None:
        """Create all tables if they don't exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS tasks (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            title               TEXT    NOT NULL,
            description         TEXT    DEFAULT '',
            tag                 TEXT    DEFAULT '',
            priority            INTEGER DEFAULT 2,
            status              TEXT    DEFAULT 'pending'
                                CHECK(status IN ('pending','done','archived')),
            created_at          TEXT    NOT NULL,
            due_date            TEXT,
            pomodoros_done      INTEGER DEFAULT 0,
            pomodoros_planned   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     INTEGER,
            start_time  TEXT    NOT NULL,
            end_time    TEXT,
            duration    INTEGER DEFAULT 0,
            type        TEXT    CHECK(type IN ('work','short_break','long_break')),
            completed   INTEGER DEFAULT 0,
            notes       TEXT    DEFAULT '',
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL
        );
        """
        try:
            self._conn.executescript(ddl)
            self._conn.commit()
            logger.debug("Schema initialised.")
        except sqlite3.Error as exc:
            logger.exception("Failed to initialise schema: %s", exc)
            raise

    # ── Generic helpers ───────────────────────────────────────────────────────

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a parameterised statement and return the cursor."""
        try:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur
        except sqlite3.Error as exc:
            logger.exception("DB execute error — sql=%s params=%s — %s", sql, params, exc)
            raise

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        try:
            return self._conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            logger.exception("DB fetchall error: %s", exc)
            raise

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        try:
            return self._conn.execute(sql, params).fetchone()
        except sqlite3.Error as exc:
            logger.exception("DB fetchone error: %s", exc)
            raise

    # ── Settings helpers ──────────────────────────────────────────────────────

    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO settings(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        try:
            self._conn.close()
            logger.info("Database connection closed.")
        except sqlite3.Error as exc:
            logger.warning("Error closing DB: %s", exc)
