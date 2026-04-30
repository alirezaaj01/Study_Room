"""
ui/main_window.py
The central hub of StudyRoom. Coordinates all widgets and core logic.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPoint, Slot, Signal
from PySide6.QtGui import QMouseEvent, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QStackedWidget, QFrame, QPushButton, QDockWidget, 
    QApplication, QSystemTrayIcon, QMenu
)

# Import Core & Media
from core.pomodoro import PomodoroEngine, PomodoroState
from core.task_manager import TaskManager
from core.session_tracker import SessionTracker
from core.app_blocker import AppBlocker
from core.hotkey_manager import HotkeyManager
from media.audio_mixer import AudioMixer
from media.bg_video_player import BackgroundVideoPlayer

# Import UI Widgets
from ui.timer_widget import TimerWidget
from ui.task_widget import TaskWidget
from ui.audio_panel import AudioPanel
from ui.stats_widget import StatsWidget
from ui.mini_player import MiniPlayer
from ui.screenshot_overlay import ScreenshotOverlay
from ui.settings_dialog import SettingsDialog
from data.settings import AppSettings

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """
    Main Application Window.
    Implements a frameless, modern UI with dockable tools and video background.
    """

    def __init__(self) -> None:
        super().__init__()
        self._init_core()
        self._setup_window()
        self._setup_background()
        self._setup_ui()
        self._setup_docks()
        self._connect_signals()
        self._apply_initial_settings()
        
        # Window dragging state
        self._drag_pos: Optional[QPoint] = None

    def _init_core(self) -> None:
        """Initialize all backend managers."""
        self._settings = AppSettings()
        self._engine = PomodoroEngine() # Config will be set via settings
        self._task_manager = TaskManager()
        self._session_tracker = SessionTracker()
        self._blocker = AppBlocker()
        self._hotkey_manager = HotkeyManager()
        self._mixer = AudioMixer()
        self._mixer.load_default_channels()

    def _setup_window(self) -> None:
        self.setWindowTitle("StudyRoom")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1100, 750)

    def _setup_background(self) -> None:
        """Setup the video background layer."""
        self._bg_player = BackgroundVideoPlayer(self)
        self.setCentralWidget(QWidget()) # Placeholder
        # Ensure video stays under all other widgets
        self._bg_player.stackUnder(self)

    def _setup_ui(self) -> None:
        """Create the main layout and navigation."""
        self.main_container = QWidget(self)
        self.setCentralWidget(self.main_container)
        
        self.main_layout = QHBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(15)

        # 1. Sidebar Navigation
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(70)
        self.sidebar.setObjectName("sidebar")
        side_layout = QVBoxLayout(self.sidebar)
        
        self._btn_timer = self._create_nav_btn("🕒", "تایمر")
        self._btn_tasks = self._create_nav_btn("📋", "وظایف")
        self._btn_stats = self._create_nav_btn("📊", "آمار")
        self._btn_settings = self._create_nav_btn("⚙", "تنظیمات")
        
        side_layout.addWidget(self._btn_timer)
        side_layout.addWidget(self._btn_tasks)
        side_layout.addWidget(self._btn_stats)
        side_layout.addStretch()
        side_layout.addWidget(self._btn_settings)

        # 2. Content Stack
        self.content_stack = QStackedWidget()
        
        self.timer_view = TimerWidget(self._engine)
        self.task_view = TaskWidget(self._task_manager)
        self.stats_view = StatsWidget(self._session_tracker)
        
        self.content_stack.addWidget(self.timer_view)
        self.content_stack.addWidget(self.task_view)
        self.content_stack.addWidget(self.stats_view)

        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content_stack, stretch=1)

    def _setup_docks(self) -> None:
        """Setup dockable widgets like the Audio Panel."""
        self.audio_dock = QDockWidget("پنل صدا", self)
        self.audio_panel = AudioPanel(self._mixer)
        self.audio_dock.setWidget(self.audio_panel)
        self.audio_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.audio_dock)

    def _create_nav_btn(self, icon: str, tooltip: str) -> QPushButton:
        btn = QPushButton(icon)
        btn.setFixedSize(50, 50)
        btn.setToolTip(tooltip)
        btn.setObjectName("navBtn")
        return btn

    def _connect_signals(self) -> None:
        """Connect UI events and Core signals [cite: 252-254]."""
        # Navigation
        self._btn_timer.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self._btn_tasks.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        self._btn_stats.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))
        self._btn_settings.clicked.connect(self._open_settings)

        # Task Selection -> Timer [cite: 254]
        self.task_view.task_selected.connect(self.timer_view.set_active_task_by_id)
        
        # Engine -> Session Tracker [cite: 254]
        self._engine.on_complete = self._on_pomodoro_complete
        self._engine.on_phase_change = self._on_phase_changed

    def _apply_initial_settings(self) -> None:
        """Load settings from DB and apply them to components."""
        # Video Background
        video_path = self._settings.get("ui.background_video")
        if video_path:
            self._bg_player.set_video(video_path)
            self._bg_player.play()
        
        # App Blocker
        self._blocker.set_blocked_apps(self._settings.blocked_apps)

    # ── Event Handlers ───────────────────────────────────────────────────────

    def _on_phase_changed(self, state: PomodoroState, count: int) -> None:
        """Handle phase changes: trigger notifications and app blocker[cite: 254]."""
        if state == PomodoroState.WORK and self._settings.get_bool("blocker.enabled_on_work"):
            self._blocker.enable_blocking()
        else:
            self._blocker.disable_blocking()
        logger.info(f"Phase changed to {state.name}. Blocker state: {self._blocker.is_enabled}")

    def _on_pomodoro_complete(self, state: PomodoroState, duration: int) -> None:
        """Record completed work sessions in the DB[cite: 254]."""
        if state == PomodoroState.WORK:
            task_id = self.timer_view.get_selected_task_id()
            self._session_tracker.start_session(state, task_id)
            self._session_tracker.end_active_session(duration, True)
            if task_id:
                self._task_manager.increment_pomodoro(task_id)
            self.task_view.refresh()
            self.stats_view.refresh()

    @Slot()
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self._blocker, self)
        dlg.settings_saved.connect(self._apply_initial_settings)
        dlg.exec()

    # ── Window Controls (Frameless Dragging) ──

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None