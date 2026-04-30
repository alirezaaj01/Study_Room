"""
ui/screenshot_overlay.py
Full-screen region selector for grabbing screenshots.
"""

from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QMouseEvent, QPainter, QPen, QScreen
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRubberBand,
    QVBoxLayout, QWidget,
)

try:
    from PIL import ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Save dialog
# ─────────────────────────────────────────────────────────────────────────────

class _SaveDialog(QDialog):
    """Ask the user for filename and destination."""

    def __init__(self, default_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ذخیره اسکرین‌شات")
        self.setMinimumWidth(400)
        self._path = default_path

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit(default_path)
        browse_btn = QPushButton("انتخاب مسیر")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, stretch=1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._copy_check = QPushButton("کپی در کلیپ‌بورد")
        self._copy_check.setCheckable(True)
        layout.addWidget(self._copy_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "مسیر ذخیره", self._path_edit.text(),
            "PNG Files (*.png);;JPEG Files (*.jpg)"
        )
        if path:
            self._path_edit.setText(path)

    @property
    def save_path(self) -> str:
        return self._path_edit.text()

    @property
    def copy_to_clipboard(self) -> bool:
        return self._copy_check.isChecked()


# ─────────────────────────────────────────────────────────────────────────────
# Overlay
# ─────────────────────────────────────────────────────────────────────────────

class ScreenshotOverlay(QWidget):
    """
    Full-screen transparent overlay for selecting a capture region.

    Usage:
        overlay = ScreenshotOverlay(save_dir="~/StudyRoom/Screenshots")
        overlay.show()

    Signals:
        screenshot_saved(str)   — path to saved file
    """

    screenshot_saved = Signal(str)

    def __init__(
        self,
        save_dir: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._save_dir = Path(save_dir).expanduser() if save_dir else (
            Path.home() / "StudyRoom" / "Screenshots"
        )
        self._save_dir.mkdir(parents=True, exist_ok=True)
        self._origin: QPoint | None = None
        self._selection: QRect = QRect()
        self._rubber: QRubberBand | None = None
        self._captured_pixmap = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # Cover all screens
        geo = QApplication.primaryScreen().availableVirtualGeometry()
        self.setGeometry(geo)
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

        if not self._selection.isNull():
            # Clear the selected area (show through)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self._selection, QColor(0, 0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            # Draw border
            pen = QPen(QColor("#6C63FF"), 2)
            painter.setPen(pen)
            painter.drawRect(self._selection)

        hint = QLabel("کلیک و بکش برای انتخاب ناحیه   |   Escape: لغو")
        painter.setPen(QColor("#E8EAF6"))
        painter.drawText(10, 24, "کلیک و بکش برای انتخاب   |   Escape: لغو")
        painter.end()

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._selection = QRect()
            if self._rubber is None:
                self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
            self._rubber.setGeometry(QRect(self._origin, self._origin))
            self._rubber.show()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._origin and self._rubber:
            self._selection = QRect(self._origin, event.position().toPoint()).normalized()
            self._rubber.setGeometry(self._selection)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._selection.isNull():
            if self._rubber:
                self._rubber.hide()
            self._capture()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    # ── Capture ───────────────────────────────────────────────────────────────

    def _capture(self) -> None:
        self.hide()
        QApplication.processEvents()

        rect = self._selection
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = str(self._save_dir / f"screenshot_{timestamp}.png")

        dlg = _SaveDialog(default_path)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.close()
            return

        save_path = dlg.save_path

        if PIL_AVAILABLE:
            # Use Pillow for accurate multi-monitor capture
            try:
                bbox = (rect.left(), rect.top(), rect.right(), rect.bottom())
                img = ImageGrab.grab(bbox=bbox, all_screens=True)
                img.save(save_path)
                logger.info("Screenshot saved to %s", save_path)
            except Exception as exc:
                logger.error("PIL capture failed: %s", exc)
                self._fallback_capture(save_path, rect)
        else:
            self._fallback_capture(save_path, rect)

        if dlg.copy_to_clipboard:
            self._copy_to_clipboard(save_path)

        self.screenshot_saved.emit(save_path)
        self.close()

    def _fallback_capture(self, path: str, rect: QRect) -> None:
        """Qt-based fallback when Pillow is unavailable."""
        screen: QScreen = QApplication.primaryScreen()
        pixmap = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
        pixmap.save(path)

    def _copy_to_clipboard(self, path: str) -> None:
        try:
            pixmap = __import__("PySide6.QtGui", fromlist=["QPixmap"]).QPixmap(path)
            QApplication.clipboard().setPixmap(pixmap)
        except Exception as exc:
            logger.warning("Could not copy to clipboard: %s", exc)
