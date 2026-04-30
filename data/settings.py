"""
data/settings.py
Typed settings layer on top of DatabaseManager.
All application configuration is read/written here.
"""

from __future__ import annotations
import json
import logging
from typing import Any

from data.database import DatabaseManager

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Default values
# ─────────────────────────────────────────────────────────────────────────────

DEFAULTS: dict[str, Any] = {
    # Pomodoro
    "pomodoro.work_minutes":            25,
    "pomodoro.short_break_minutes":     5,
    "pomodoro.long_break_minutes":      15,
    "pomodoro.sessions_before_long":    4,
    "pomodoro.auto_start_breaks":       False,
    "pomodoro.auto_start_work":         False,

    # Audio
    "audio.master_volume":              70,
    "audio.channel_state":             "{}",   # JSON dict: {name: volume}

    # UI / Theme
    "ui.theme":                         "dark",
    "ui.accent_color":                  "#6C63FF",
    "ui.background_video":              "",
    "ui.video_opacity":                 0.6,
    "ui.video_blur":                    5,
    "ui.window_geometry":               "",    # base64 encoded QByteArray

    # App blocker
    "blocker.apps":                     "[]",  # JSON list of process names
    "blocker.enabled_on_work":          True,

    # Workspaces
    "workspaces.list":                  "[]",  # JSON list of workspace dicts

    # Hotkeys
    "hotkey.screenshot":                "ctrl+shift+s",
    "hotkey.timer_toggle":              "ctrl+shift+t",
    "hotkey.mini_mode":                 "ctrl+shift+m",
    "hotkey.blocker_toggle":            "ctrl+shift+b",

    # Misc
    "app.first_run":                    True,
}


# ─────────────────────────────────────────────────────────────────────────────
# AppSettings
# ─────────────────────────────────────────────────────────────────────────────

class AppSettings:
    """
    Typed wrapper around DatabaseManager settings table.
    All get/set operations go through this class.
    """

    def __init__(self) -> None:
        self._db = DatabaseManager.instance()
        self._cache: dict[str, Any] = {}
        self._populate_defaults()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _populate_defaults(self) -> None:
        """Insert default values for keys that don't exist yet."""
        for key, value in DEFAULTS.items():
            existing = self._db.get_setting(key)
            if existing is None:
                self._db.set_setting(key, value)

    def _raw_get(self, key: str) -> str:
        default = DEFAULTS.get(key, "")
        return self._db.get_setting(key, str(default))

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Return the raw string value for key."""
        val = self._db.get_setting(key)
        if val is None:
            return default if default is not None else DEFAULTS.get(key)
        return val

    def get_int(self, key: str) -> int:
        return int(self._raw_get(key))

    def get_float(self, key: str) -> float:
        return float(self._raw_get(key))

    def get_bool(self, key: str) -> bool:
        val = self._raw_get(key).lower()
        return val in ("1", "true", "yes")

    def get_json(self, key: str) -> Any:
        raw = self._raw_get(key)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Could not parse JSON for key=%s, returning default.", key)
            return json.loads(str(DEFAULTS.get(key, "null")))

    def set(self, key: str, value: Any) -> None:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        self._db.set_setting(key, value)
        logger.debug("Setting saved: %s = %s", key, value)

    def set_many(self, mapping: dict[str, Any]) -> None:
        for key, value in mapping.items():
            self.set(key, value)

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def work_minutes(self) -> int:
        return self.get_int("pomodoro.work_minutes")

    @property
    def short_break_minutes(self) -> int:
        return self.get_int("pomodoro.short_break_minutes")

    @property
    def long_break_minutes(self) -> int:
        return self.get_int("pomodoro.long_break_minutes")

    @property
    def sessions_before_long(self) -> int:
        return self.get_int("pomodoro.sessions_before_long")

    @property
    def theme(self) -> str:
        return self.get("ui.theme", "dark")

    @property
    def accent_color(self) -> str:
        return self.get("ui.accent_color", "#6C63FF")

    @property
    def blocked_apps(self) -> list[str]:
        return self.get_json("blocker.apps")

    @property
    def workspaces(self) -> list[dict]:
        return self.get_json("workspaces.list")

    @property
    def channel_state(self) -> dict[str, float]:
        return self.get_json("audio.channel_state")
