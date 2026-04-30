"""
ui/mini_player.py
Compact always-on-top player: timer display + play/pause + volume.
"""

from __future__ import annotations
import logging

from PySide6.QtCore import Qt, QPoint, Signal, Slot
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QWidget,
)

from core.pomodoro import PomodoroEngine, PomodoroState

logger = logging.getLogger(__name__)


class MiniPlayer(QWidget):
    """
    A 320×80 frameless, always-on-top mini overlay.
    Double-click to return to full window.

    Signals:
        restore_requested()   — user wants to go back to MainWindow
    """

    restore_requested = Signal()

    def __init__(self, engine: PomodoroEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._drag_pos: QPoint | None = None
        self._setup_window()
        self._setup_ui()
        self._connect_engine()

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setObjectName("miniPlayer")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 80)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Phase indicator dot
        self._dot = QLabel("●")
        self._dot.setStyleSheet("color: #6C63FF; font-size: 10px;")
        self._dot.setFixedWidth(14)
        layout.addWidget(self._dot)

        # Timer display
        self._time_label = QLabel("25:00")
        self._time_label.setStyleSheet(
            "color: #E8EAF6; font-size: 20px; font-weight: 700; letter-spacing: 2px;"
        )
        layout.addWidget(self._time_label)

        layout.addStretch()

        # Play/Pause button
        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("iconBtn")
        self._play_btn.setFixedSize(32, 32)
        self._play_btn.setStyleSheet(
            "QPushButton { background: #2D3245; border-radius: 16px; color: #E8EAF6; font-size: 12px; }"
            "QPushButton:hover { background: #6C63FF; }"
        )
        self._play_btn.clicked.connect(self._on_play_pause)
        layout.addWidget(self._play_btn)

        # Skip button
        skip_btn = QPushButton("⏭")
        skip_btn.setObjectName("iconBtn")
        skip_btn.setFixedSize(32, 32)
        skip_btn.setStyleSheet(self._play_btn.styleSheet())
        skip_btn.clicked.connect(self._on_skip)
        layout.addWidget(skip_btn)

        # Volume slider
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(70)
        self._vol_slider.setFixedWidth(60)
        self._vol_slider.setStyleSheet(
            "QSlider::groove:horizontal { background:#2D3245; height:3px; border-radius:1px;}"
            "QSlider::handle:horizontal { background:#6C63FF; width:10px; height:10px; border-radius:5px; margin:-3px 0;}"
            "QSlider::sub-page:horizontal { background:#6C63FF; border-radius:1px;}"
        )
        layout.addWidget(self._vol_slider)

        # Close/restore button
        restore_btn = QPushButton("⤡")
        restore_btn.setObjectName("iconBtn")
        restore_btn.setFixedSize(24, 24)
        restore_btn.setToolTip("بازگشت به پنجره اصلی")
        restore_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #9E9E9E; font-size: 14px; border: none; }"
            "QPushButton:hover { color: #E8EAF6; }"
        )
        restore_btn.clicked.connect(self.restore_requested)
        layout.addWidget(restore_btn)

    # ── Engine connection ─────────────────────────────────────────────────────

    def _connect_engine(self) -> None:
        self._engine.on_tick         = self._on_engine_tick
        self._engine.on_phase_change = self._on_engine_phase_change

    def _on_engine_tick(
        self, state: PomodoroState, remaining: int, total: int
    ) -> None:
        mm = remaining // 60
        ss = remaining % 60
        self._time_label.setText(f"{mm:02d}:{ss:02d}")

    def _on_engine_phase_change(
        self, state: PomodoroState, session_count: int
    ) -> None:
        color_map = {
            PomodoroState.WORK:        "#4CAF50",
            PomodoroState.SHORT_BREAK: "#FF9800",
            PomodoroState.LONG_BREAK:  "#6C63FF",
            PomodoroState.IDLE:        "#9E9E9E",
            PomodoroState.PAUSED:      "#9E9E9E",
        }
        color = color_map.get(state, "#9E9E9E")
        self._dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        is_running = state not in (PomodoroState.IDLE, PomodoroState.PAUSED)
        self._play_btn.setText("⏸" if is_running else "▶")

    # ── Drag ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.restore_requested.emit()

    # ── Button handlers ───────────────────────────────────────────────────────

    @Slot()
    def _on_play_pause(self) -> None:
        state = self._engine.state
        if state == PomodoroState.IDLE:
            self._engine.start()
            self._play_btn.setText("⏸")
        elif state == PomodoroState.PAUSED:
            self._engine.resume()
            self._play_btn.setText("⏸")
        else:
            self._engine.pause()
            self._play_btn.setText("▶")

    @Slot()
    def _on_skip(self) -> None:
        self._engine.skip()

    # ── Public ────────────────────────────────────────────────────────────────

    def volume_value(self) -> int:
        return self._vol_slider.value()
