"""
core/hotkey_manager.py
Global hotkey registration using the `keyboard` library.
Runs listener in a daemon thread so it never blocks the UI.
"""

from __future__ import annotations
import logging
import threading
from typing import Callable, Optional

try:
    import keyboard as _keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "keyboard library not installed — global hotkeys disabled."
    )

logger = logging.getLogger(__name__)


class HotkeyManager:
    """
    Registers and manages global keyboard shortcuts.

    All callbacks are invoked on the keyboard listener thread.
    If you need to update PySide6 widgets from the callback, emit a
    Qt signal instead of calling widget methods directly.

    Default hotkeys (can be changed via settings):
        Ctrl+Shift+S  — screenshot
        Ctrl+Shift+T  — timer toggle
        Ctrl+Shift+M  — mini mode
        Ctrl+Shift+B  — blocker toggle
    """

    def __init__(self) -> None:
        self._hooks: dict[str, object] = {}   # hotkey_str -> hook handle
        self._callbacks: dict[str, Callable] = {}
        self._lock = threading.Lock()

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, hotkey: str, callback: Callable[[], None]) -> bool:
        """
        Register a global hotkey.
        Returns True on success, False if keyboard lib unavailable.
        """
        if not KEYBOARD_AVAILABLE:
            return False
        with self._lock:
            if hotkey in self._hooks:
                self.unregister(hotkey)
            try:
                handle = _keyboard.add_hotkey(hotkey, callback, suppress=False)
                self._hooks[hotkey] = handle
                self._callbacks[hotkey] = callback
                logger.info("Registered hotkey: %s", hotkey)
                return True
            except Exception as exc:
                logger.error("Failed to register hotkey %r: %s", hotkey, exc)
                return False

    def unregister(self, hotkey: str) -> None:
        if not KEYBOARD_AVAILABLE:
            return
        with self._lock:
            if hotkey in self._hooks:
                try:
                    _keyboard.remove_hotkey(self._hooks[hotkey])
                except Exception as exc:
                    logger.debug("Error removing hotkey %r: %s", hotkey, exc)
                del self._hooks[hotkey]
                self._callbacks.pop(hotkey, None)
                logger.info("Unregistered hotkey: %s", hotkey)

    def unregister_all(self) -> None:
        """Call this when the application exits."""
        if not KEYBOARD_AVAILABLE:
            return
        for hotkey in list(self._hooks.keys()):
            self.unregister(hotkey)
        logger.info("All hotkeys unregistered.")

    def is_registered(self, hotkey: str) -> bool:
        return hotkey in self._hooks

    def get_registered(self) -> list[str]:
        return list(self._hooks.keys())

    def re_register(self, old_hotkey: str, new_hotkey: str) -> bool:
        """Change a registered hotkey to a new combination."""
        if old_hotkey in self._callbacks:
            callback = self._callbacks[old_hotkey]
            self.unregister(old_hotkey)
            return self.register(new_hotkey, callback)
        return False

    # ── Bulk setup ────────────────────────────────────────────────────────────

    def setup_defaults(
        self,
        on_screenshot: Callable,
        on_timer_toggle: Callable,
        on_mini_mode: Callable,
        on_blocker_toggle: Callable,
        hotkeys: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Register all default application hotkeys.

        hotkeys dict maps action names to key combos, e.g.:
        {"screenshot": "ctrl+shift+s", "timer_toggle": "ctrl+shift+t"}
        """
        hk = hotkeys or {}
        mapping = {
            hk.get("screenshot",     "ctrl+shift+s"): on_screenshot,
            hk.get("timer_toggle",   "ctrl+shift+t"): on_timer_toggle,
            hk.get("mini_mode",      "ctrl+shift+m"): on_mini_mode,
            hk.get("blocker_toggle", "ctrl+shift+b"): on_blocker_toggle,
        }
        for combo, cb in mapping.items():
            self.register(combo, cb)
