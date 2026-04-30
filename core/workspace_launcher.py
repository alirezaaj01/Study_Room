"""
core/workspace_launcher.py
Save, load, and launch study workspace recipes.
"""

from __future__ import annotations
import json
import logging
import platform
import subprocess
import os
from pathlib import Path
from typing import Optional

from data.models import Workspace
from data.settings import AppSettings

logger = logging.getLogger(__name__)
OS = platform.system()


class WorkspaceLauncher:
    """Manages saved workspaces and launches them at session start."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    # ── Persistence ───────────────────────────────────────────────────────────

    def save_workspace(self, workspace: Workspace) -> None:
        """Add or update a workspace in the settings store."""
        workspaces = self.load_workspaces()
        # Replace existing by name
        workspaces = [w for w in workspaces if w.name != workspace.name]
        workspaces.append(workspace)
        self._settings.set(
            "workspaces.list",
            json.dumps([w.to_dict() for w in workspaces], ensure_ascii=False),
        )
        logger.info("Workspace saved: %s", workspace.name)

    def load_workspaces(self) -> list[Workspace]:
        raw = self._settings.get_json("workspaces.list")
        if not isinstance(raw, list):
            return []
        result = []
        for item in raw:
            try:
                result.append(Workspace.from_dict(item))
            except Exception as exc:
                logger.warning("Could not load workspace: %s", exc)
        return result

    def get_workspace(self, name: str) -> Optional[Workspace]:
        for ws in self.load_workspaces():
            if ws.name == name:
                return ws
        return None

    def delete_workspace(self, name: str) -> None:
        workspaces = [w for w in self.load_workspaces() if w.name != name]
        self._settings.set(
            "workspaces.list",
            json.dumps([w.to_dict() for w in workspaces], ensure_ascii=False),
        )

    # ── Launch ────────────────────────────────────────────────────────────────

    def launch(self, workspace: Workspace) -> None:
        """Open all apps and files defined in the workspace."""
        logger.info("Launching workspace: %s", workspace.name)

        for app_path in workspace.apps:
            self._open_executable(app_path)

        for file_path in workspace.files:
            self._open_file(file_path)

        if workspace.do_not_disturb:
            self.set_do_not_disturb(True)

    def _open_executable(self, path: str) -> None:
        if not path:
            return
        try:
            subprocess.Popen([path], close_fds=True)
            logger.info("Launched app: %s", path)
        except Exception as exc:
            logger.error("Failed to launch %r: %s", path, exc)

    def _open_file(self, path: str) -> None:
        if not path or not Path(path).exists():
            logger.warning("File not found: %s", path)
            return
        try:
            if OS == "Windows":
                os.startfile(path)
            elif OS == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            logger.info("Opened file: %s", path)
        except Exception as exc:
            logger.error("Failed to open file %r: %s", path, exc)

    # ── Do Not Disturb ────────────────────────────────────────────────────────

    def set_do_not_disturb(self, enabled: bool) -> None:
        """
        Enable/disable system Do Not Disturb mode.
        Best-effort — silently fails on unsupported configurations.
        """
        try:
            if OS == "Darwin":
                # macOS: use shortcuts / AppleScript
                state = "true" if enabled else "false"
                script = (
                    f'tell application "System Events" to '
                    f'tell dock preferences to set do not disturb to {state}'
                )
                subprocess.run(["osascript", "-e", script], check=False, timeout=5)

            elif OS == "Linux":
                # GNOME — ignore errors if not available
                value = "true" if enabled else "false"
                subprocess.run(
                    ["gsettings", "set", "org.gnome.desktop.notifications",
                     "show-banners", str(not enabled).lower()],
                    check=False, timeout=5,
                )

            # Windows: Focus Assist cannot be set programmatically reliably
            logger.info("Do Not Disturb set to %s on %s", enabled, OS)
        except Exception as exc:
            logger.debug("set_do_not_disturb failed: %s", exc)
