"""
core/app_blocker.py
Suspend / resume OS processes by name using psutil.
Works on Windows, Linux, and macOS.
"""

from __future__ import annotations
import logging
import platform
import sys
from typing import Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "psutil not installed — AppBlocker will be disabled."
    )

logger = logging.getLogger(__name__)
OS = platform.system()   # 'Windows' | 'Linux' | 'Darwin'


class AppBlocker:
    """
    Manages a list of process names to block during focus sessions.

    Usage:
        blocker = AppBlocker()
        blocker.add_blocked_app("telegram.exe")
        blocker.enable_blocking()     # suspends matching processes
        blocker.disable_blocking()    # resumes them
    """

    def __init__(self) -> None:
        self._blocked_names: list[str] = []          # lowercase process names
        self._suspended_pids: dict[int, str] = {}    # pid -> name (currently suspended)
        self._enabled: bool = False

    # ── Config ────────────────────────────────────────────────────────────────

    def set_blocked_apps(self, names: list[str]) -> None:
        """Replace the entire block list."""
        self._blocked_names = [n.lower() for n in names]
        logger.debug("Block list set to: %s", self._blocked_names)

    def add_blocked_app(self, process_name: str) -> None:
        name = process_name.lower()
        if name not in self._blocked_names:
            self._blocked_names.append(name)

    def remove_blocked_app(self, process_name: str) -> None:
        name = process_name.lower()
        if name in self._blocked_names:
            self._blocked_names.remove(name)

    def get_blocked_apps(self) -> list[str]:
        return list(self._blocked_names)

    # ── Runtime ───────────────────────────────────────────────────────────────

    def enable_blocking(self) -> None:
        """Suspend all running processes whose name is in the block list."""
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil unavailable — cannot block apps.")
            return
        self._enabled = True
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info["name"] or "").lower()
                if pname in self._blocked_names and proc.pid not in self._suspended_pids:
                    proc.suspend()
                    self._suspended_pids[proc.pid] = pname
                    logger.info("Suspended PID %d (%s)", proc.pid, pname)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as exc:
                logger.debug("Could not suspend PID %s: %s", proc.pid, exc)

    def disable_blocking(self) -> None:
        """Resume all suspended processes."""
        if not PSUTIL_AVAILABLE:
            return
        self._enabled = False
        to_remove: list[int] = []
        for pid, name in self._suspended_pids.items():
            try:
                proc = psutil.Process(pid)
                proc.resume()
                logger.info("Resumed PID %d (%s)", pid, name)
                to_remove.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                logger.debug("Could not resume PID %d: %s", pid, exc)
                to_remove.append(pid)   # remove stale entry anyway
        for pid in to_remove:
            del self._suspended_pids[pid]

    def toggle(self) -> bool:
        """Toggle blocking on/off. Returns new state (True = enabled)."""
        if self._enabled:
            self.disable_blocking()
        else:
            self.enable_blocking()
        return self._enabled

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def get_running_blocked(self) -> list[str]:
        """Return names of blocked processes currently running."""
        if not PSUTIL_AVAILABLE:
            return []
        running = []
        for proc in psutil.process_iter(["name"]):
            try:
                pname = (proc.info["name"] or "").lower()
                if pname in self._blocked_names:
                    running.append(pname)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return list(set(running))
