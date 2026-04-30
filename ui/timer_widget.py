"""
ui/timer_widget.py
Pomodoro timer display widget.  Connects to PomodoroEngine via callbacks.
"""

from __future__ import annotations
import logging
import math
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from core.pomodoro import PomodoroEngine, PomodoroState
from data.models import Task

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Circular progress ring
# ─────────────────────────────────────────────────────────────────────────────

class _RingWidget(QWidget):
    """Draws a circular progress arc."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._progress: float = 1.0   # 0.0 – 1.0
        self._color: QColor = QColor("#6C63FF")
        self.setMinimumSize(220, 220)

    def set_progress(self, progress: float, color: QColor | None = None) -> None:
        self._progress = max(0.0, min(1.0, progress))
        if color:
            self._color = color
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(10, 10, -10, -10)

        # Background ring
        bg_pen = QPen(QColor("#2D3245"), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Progress ring (start at top = 90°, clockwise)
        if self._progress > 0:
            prog_pen = QPen(self._color, 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(prog_pen)
            span = int(self._progress * 360 * 16)
            painter.drawArc(rect, 90 * 16, -span)

        painter.end()


# ─────────────────────────────────────────────────────────────────────────────
# TimerWidget
# ─────────────────────────────────────────────────────────────────────────────

class TimerWidget(QWidget):
    """
    Full Pomodoro timer panel.
    """
    start_requested  = Signal()
    pause_requested  = Signal()
    stop_requested   = Signal()
    skip_requested   = Signal()

    _PHASE_COLORS = {
        PomodoroState.WORK:        QColor("#4CAF50"),
        PomodoroState.SHORT_BREAK: QColor("#FF9800"),
        PomodoroState.LONG_BREAK:  QColor("#6C63FF"),
        PomodoroState.IDLE:        QColor("#6C63FF"),
        PomodoroState.PAUSED:      QColor("#9E9E9E"),
    }

    _PHASE_LABELS = {
        PomodoroState.WORK:        "کار",
        PomodoroState.SHORT_BREAK: "استراحت کوتاه",
        PomodoroState.LONG_BREAK:  "استراحت طولانی",
        PomodoroState.IDLE:        "آماده",
        PomodoroState.PAUSED:      "مکث",
    }

    def __init__(self, engine: PomodoroEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._active_task_id: Optional[int] = None
        self._is_running = False
        self._setup_ui()
        self._connect_engine()

        self._qtimer = QTimer(self)
        self._qtimer.setInterval(1000)
        self._qtimer.timeout.connect(self._on_timer_tick)

    def _setup_ui(self) -> None:
        self.setObjectName("timerPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Phase label
        self._phase_label = QLabel("آماده")
        self._phase_label.setObjectName("phaseLabel")
        self._phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._phase_label)

        # استفاده از Layout برای مرکز نگه داشتن متن تایمر درون حلقه
        self._ring = _RingWidget()
        self._ring.setFixedSize(220, 220)
        
        ring_layout = QVBoxLayout(self._ring)
        ring_layout.setContentsMargins(0, 0, 0, 0)
        
        self._time_label = QLabel("25:00")
        self._time_label.setObjectName("timerLabel")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ring_layout.addWidget(self._time_label, alignment=Qt.AlignmentFlag.AlignCenter)

        root.addWidget(self._ring, alignment=Qt.AlignmentFlag.AlignCenter)

        # Session count
        self._session_label = QLabel("نشست ۰")
        self._session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._session_label.setObjectName("statCaption")
        root.addWidget(self._session_label)

        # Task selector
        task_row = QHBoxLayout()
        task_row.addWidget(QLabel("وظیفه:"))
        self._task_combo = QComboBox()
        self._task_combo.addItem("— بدون وظیفه —", None)
        task_row.addWidget(self._task_combo, stretch=1)
        root.addLayout(task_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._start_btn = QPushButton("شروع")
        self._start_btn.setProperty("role", "primary")
        self._start_btn.setObjectName("primaryBtn")
        self._start_btn.setMinimumWidth(90)

        self._skip_btn = QPushButton("رد کن")
        self._skip_btn.setEnabled(False)

        self._stop_btn = QPushButton("توقف")
        self._stop_btn.setProperty("role", "danger")
        self._stop_btn.setEnabled(False)

        btn_row.addWidget(self._stop_btn)
        btn_row.addWidget(self._start_btn, stretch=1)
        btn_row.addWidget(self._skip_btn)
        root.addLayout(btn_row)

        self._start_btn.clicked.connect(self._on_start_clicked)
        self._stop_btn.clicked.connect(self.stop_requested)
        self._skip_btn.clicked.connect(self.skip_requested)

    def _connect_engine(self) -> None:
        self._engine.on_tick         = self._on_engine_tick
        self._engine.on_phase_change = self._on_engine_phase_change
        self._engine.on_complete     = self._on_engine_complete

    def _on_engine_tick(self, state: PomodoroState, remaining: int, total: int) -> None:
        mm = remaining // 60
        ss = remaining % 60
        self._time_label.setText(f"{mm:02d}:{ss:02d}")

        progress = remaining / total if total > 0 else 1.0
        color = self._PHASE_COLORS.get(state, QColor("#6C63FF"))
        self._ring.set_progress(progress, color)

    def _on_engine_phase_change(self, state: PomodoroState, session_count: int) -> None:
        label = self._PHASE_LABELS.get(state, "")
        self._phase_label.setText(label)
        self._session_label.setText(f"نشست {session_count}")

        color = self._PHASE_COLORS.get(state, QColor("#6C63FF"))
        self._ring.set_progress(1.0, color)

        is_active = state not in (PomodoroState.IDLE,)
        self._stop_btn.setEnabled(is_active)
        self._skip_btn.setEnabled(is_active)

        if state == PomodoroState.IDLE:
            self._time_label.setText("00:00")
            self._start_btn.setText("شروع")
            self._is_running = False
            self._qtimer.stop()

    def _on_engine_complete(self, completed_state: PomodoroState, duration: int) -> None:
        logger.info("Phase complete: %s (%ds)", completed_state.name, duration)

    @Slot()
    def _on_timer_tick(self) -> None:
        self._engine.tick()

    def _on_start_clicked(self) -> None:
        state = self._engine.state
        if state == PomodoroState.IDLE:
            self._engine.start()
            self._qtimer.start()
            self._start_btn.setText("مکث")
            self._is_running = True
            self.start_requested.emit()
        elif state == PomodoroState.PAUSED:
            self._engine.resume()
            self._qtimer.start()
            self._start_btn.setText("مکث")
            self._is_running = True
        else:
            self._engine.pause()
            self._qtimer.stop()
            self._start_btn.setText("ادامه")
            self._is_running = False
            self.pause_requested.emit()

    def set_tasks(self, tasks: list[Task]) -> None:
        self._task_combo.clear()
        self._task_combo.addItem("— بدون وظیفه —", None)
        for task in tasks:
            self._task_combo.addItem(f"[{task.tag}] {task.title}" if task.tag else task.title, task.id)

    def get_selected_task_id(self) -> Optional[int]:
        return self._task_combo.currentData()

    def set_display(self, minutes: int, seconds: int = 0) -> None:
        self._time_label.setText(f"{minutes:02d}:{seconds:02d}")

    @Slot()
    def stop(self) -> None:
        self._engine.stop()
        self._qtimer.stop()
        self._start_btn.setText("شروع")
        self._stop_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._is_running = False

    @Slot()
    def skip(self) -> None:
        self._engine.skip()

    @Slot(int)
    def set_active_task_by_id(self, task_id: int) -> None:
        for i in range(self._task_combo.count()):
            if self._task_combo.itemData(i) == task_id:
                self._task_combo.setCurrentIndex(i)
                break