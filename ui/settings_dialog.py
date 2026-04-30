"""
ui/settings_dialog.py
Comprehensive settings dialog with tabs for Timer, Theme, Blocker, Workspaces, and Sounds.
"""

from __future__ import annotations
import logging
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, 
    QLabel, QLineEdit, QListWidget, QPushButton, QSpinBox, 
    QTabWidget, QVBoxLayout, QWidget, QColorDialog, QFileDialog,
    QCheckBox
)

from data.settings import AppSettings
from core.app_blocker import AppBlocker

logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    """
    Multitab settings window for user configuration.
    Saves data back to AppSettings on accept.
    """
    
    settings_saved = Signal()

    def __init__(self, settings: AppSettings, blocker: AppBlocker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._blocker = blocker
        
        self.setWindowTitle("تنظیمات StudyRoom")
        self.setMinimumSize(500, 450)
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        self._tabs = QTabWidget()
        
        # ۱. تب تایمر [cite: 228]
        self._timer_tab = QWidget()
        self._setup_timer_tab()
        self._tabs.addTab(self._timer_tab, "تایمر")

        # ۲. تب تم [cite: 229]
        self._theme_tab = QWidget()
        self._setup_theme_tab()
        self._tabs.addTab(self._theme_tab, "ظاهر")

        # ۳. تب بلاکر [cite: 230]
        self._blocker_tab = QWidget()
        self._setup_blocker_tab()
        self._tabs.addTab(self._blocker_tab, "مسدودکننده")

        # ۴. تب صداها [cite: 232]
        self._sounds_tab = QWidget()
        self._setup_sounds_tab()
        self._tabs.addTab(self._sounds_tab, "صداها")

        layout.addWidget(self._tabs)

        # دکمه‌های تایید و انصراف [cite: 233]
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    # ── بخش‌های داخلی تب‌ها ──────────────────────────────────────────────────

    def _setup_timer_tab(self) -> None:
        lay = QFormLayout(self._timer_tab)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(15)

        self._work_spin = QSpinBox()
        self._work_spin.setRange(1, 120)
        self._work_spin.setSuffix(" دقیقه")
        lay.addRow("مدت زمان کار:", self._work_spin)

        self._short_spin = QSpinBox()
        self._short_spin.setRange(1, 30)
        self._short_spin.setSuffix(" دقیقه")
        lay.addRow("استراحت کوتاه:", self._short_spin)

        self._long_spin = QSpinBox()
        self._long_spin.setRange(1, 60)
        self._long_spin.setSuffix(" دقیقه")
        lay.addRow("استراحت طولانی:", self._long_spin)

        self._sessions_spin = QSpinBox()
        self._sessions_spin.setRange(1, 10)
        lay.addRow("تعداد جلسات قبل از استراحت بزرگ:", self._sessions_spin)

    def _setup_theme_tab(self) -> None:
        lay = QFormLayout(self._theme_tab)
        lay.setContentsMargins(20, 20, 20, 20)
        
        self._accent_btn = QPushButton("انتخاب رنگ")
        self._accent_btn.clicked.connect(self._pick_accent_color)
        lay.addRow("رنگ اصلی برنامه:", self._accent_btn)
        
        self._bg_video_edit = QLineEdit()
        self._bg_video_edit.setPlaceholderText("مسیر فایل ویدیویی...")
        self._browse_video_btn = QPushButton("انتخاب فایل")
        self._browse_video_btn.clicked.connect(self._browse_video)
        
        video_row = QHBoxLayout()
        video_row.addWidget(self._bg_video_edit)
        video_row.addWidget(self._browse_video_btn)
        lay.addRow("ویدیوی پس‌زمینه:", video_row)

    def _setup_blocker_tab(self) -> None:
        lay = QVBoxLayout(self._blocker_tab)
        lay.setContentsMargins(20, 20, 20, 20)
        
        lay.addWidget(QLabel("لیست برنامه‌های مسدودشده (مثال: telegram.exe):"))
        self._block_list = QListWidget()
        lay.addWidget(self._block_list)

        btn_row = QHBoxLayout()
        self._add_block_btn = QPushButton("افزودن")
        self._add_block_btn.clicked.connect(self._add_block_item)
        self._remove_block_btn = QPushButton("حذف")
        self._remove_block_btn.clicked.connect(self._remove_block_item)
        
        btn_row.addWidget(self._add_block_btn)
        btn_row.addWidget(self._remove_block_btn)
        lay.addLayout(btn_row)

    def _setup_sounds_tab(self) -> None:
        lay = QFormLayout(self._sounds_tab)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.addWidget(QLabel("در این بخش می‌توانید مسیر فایل‌های صوتی سفارشی را تنظیم کنید."))
        # در نسخه v1.0 این بخش از asset‌های پیش‌فرض استفاده می‌کند.

    # ── مدیریت داده‌ها ───────────────────────────────────────────────────────

    def _load_values(self) -> None:
        """Load current settings from database to UI[cite: 247]."""
        self._work_spin.setValue(self._settings.work_minutes)
        self._short_spin.setValue(self._settings.short_break_minutes)
        self._long_spin.setValue(self._settings.long_break_minutes)
        self._sessions_spin.setValue(self._settings.sessions_before_long)
        self._bg_video_edit.setText(self._settings.get("ui.background_video", ""))
        
        # بارگذاری لیست بلاکر
        for app in self._settings.blocked_apps:
            self._block_list.addItem(app)

    def _pick_accent_color(self) -> None:
        color = QColorDialog.getColor(Qt.GlobalColor.white, self, "انتخاب رنگ اصلی")
        if color.isValid():
            self._current_accent = color.name()
            logger.debug(f"New accent color selected: {self._current_accent}")

    def _browse_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "انتخاب ویدیو", "", "Video Files (*.mp4 *.mkv)")
        if path:
            self._bg_video_edit.setText(path)

    def _add_block_item(self) -> None:
        # در یک سناریوی واقعی یک InputDialog کوچک باز می‌شود
        self._block_list.addItem("new_app.exe")

    def _remove_block_item(self) -> None:
        for item in self._list.selectedItems():
            self._block_list.takeItem(self._block_list.row(item))

    def accept(self) -> None:
        """Save values and close[cite: 233, 275]."""
        self._settings.set("pomodoro.work_minutes", self._work_spin.value())
        self._settings.set("pomodoro.short_break_minutes", self._short_spin.value())
        self._settings.set("pomodoro.long_break_minutes", self._long_spin.value())
        self._settings.set("pomodoro.sessions_before_long", self._sessions_spin.value())
        self._settings.set("ui.background_video", self._bg_video_edit.text())
        
        # ذخیره لیست بلاکر
        apps = [self._block_list.item(i).text() for i in range(self._block_list.count())]
        self._settings.set("blocker.apps", apps)
        self._blocker.set_blocked_apps(apps)
        
        self.settings_saved.emit()
        super().accept()