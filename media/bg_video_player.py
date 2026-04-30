"""
media/bg_video_player.py
Looping video background widget that sits behind all other widgets.
"""

from __future__ import annotations
import logging
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsOpacityEffect, QWidget, QVBoxLayout

logger = logging.getLogger(__name__)


class BackgroundVideoPlayer(QWidget):
    """
    A QWidget that plays a looping video behind all other content.

    Place this widget in the main layout *before* other widgets, then call
    stackUnder() or manage z-order so other content renders on top.

    Usage:
        bg = BackgroundVideoPlayer(parent)
        bg.set_video("/path/to/lofi.mp4")
        bg.play()
        bg.set_opacity(0.6)
        bg.set_blur(4)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Video widget
        self._video_widget = QVideoWidget(self)
        self._video_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._video_widget)

        # Media player
        self._player = QMediaPlayer(self)
        self._player.setVideoOutput(self._video_widget)
        self._player.setLoops(QMediaPlayer.Loops.Infinite)
        self._player.errorOccurred.connect(self._on_error)

        # Effects
        self._opacity_effect = QGraphicsOpacityEffect(self._video_widget)
        self._opacity_effect.setOpacity(1.0)
        self._video_widget.setGraphicsEffect(self._opacity_effect)

        self._blur_effect: QGraphicsBlurEffect | None = None
        self._current_file: str = ""

    # ── File management ───────────────────────────────────────────────────────

    def set_video(self, file_path: str) -> None:
        """Set the video source. Stops current playback."""
        if not file_path:
            self._player.stop()
            self._current_file = ""
            return
        if not Path(file_path).exists():
            logger.warning("Video file not found: %s", file_path)
            return
        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(file_path))
        self._current_file = file_path
        logger.info("Video source set: %s", file_path)

    def current_file(self) -> str:
        return self._current_file

    # ── Playback ──────────────────────────────────────────────────────────────

    def play(self) -> None:
        if self._current_file:
            self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    @property
    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    # ── Visual effects ────────────────────────────────────────────────────────

    def set_opacity(self, value: float) -> None:
        """Set video opacity. value in [0.0, 1.0]."""
        value = max(0.0, min(1.0, value))
        self._opacity_effect.setOpacity(value)

    def set_blur(self, radius: int) -> None:
        """Apply a blur effect. radius=0 disables blur."""
        if radius <= 0:
            if self._blur_effect is not None:
                self._video_widget.setGraphicsEffect(self._opacity_effect)
                self._blur_effect = None
            return
        # Stack blur on top of opacity
        self._blur_effect = QGraphicsBlurEffect(self._video_widget)
        self._blur_effect.setBlurRadius(radius)
        self._video_widget.setGraphicsEffect(self._blur_effect)

    def set_visible(self, visible: bool) -> None:
        self.setVisible(visible)

    # ── Error handling ────────────────────────────────────────────────────────

    def _on_error(self, error, error_string: str) -> None:
        logger.error("BackgroundVideoPlayer error: %s — %s", error, error_string)
