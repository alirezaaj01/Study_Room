"""
ui/task_widget.py
To-Do list panel: add, edit, complete, delete, filter tasks.
"""

from __future__ import annotations
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from core.task_manager import TaskManager
from data.models import Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)

# Priority badge colours
_PRIORITY_COLORS = {
    TaskPriority.HIGH:   "#F44336",
    TaskPriority.MEDIUM: "#FF9800",
    TaskPriority.LOW:    "#4CAF50",
}


# ─────────────────────────────────────────────────────────────────────────────
# Add / Edit Dialog
# ─────────────────────────────────────────────────────────────────────────────

class TaskDialog(QDialog):
    """Dialog for creating or editing a task."""

    def __init__(
        self,
        parent: QWidget | None = None,
        task: Optional[Task] = None,
        existing_tags: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._task = task
        self.setWindowTitle("ویرایش وظیفه" if task else "وظیفه جدید")
        self.setMinimumWidth(380)
        self._build_ui(existing_tags or [])
        if task:
            self._populate(task)

    def _build_ui(self, tags: list[str]) -> None:
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("عنوان وظیفه …")
        layout.addRow("عنوان:", self._title_edit)

        self._tag_combo = QComboBox()
        self._tag_combo.setEditable(True)
        self._tag_combo.addItem("")
        self._tag_combo.addItems(tags)
        layout.addRow("برچسب:", self._tag_combo)

        self._priority_combo = QComboBox()
        for p in TaskPriority:
            self._priority_combo.addItem(p.name.capitalize(), p)
        self._priority_combo.setCurrentIndex(1)   # MEDIUM
        layout.addRow("اولویت:", self._priority_combo)

        self._pomodoro_spin = QSpinBox()
        self._pomodoro_spin.setRange(1, 20)
        self._pomodoro_spin.setValue(1)
        layout.addRow("تعداد پومودورو:", self._pomodoro_spin)

        self._due_edit = QDateEdit()
        self._due_edit.setCalendarPopup(True)
        self._due_edit.setSpecialValueText("بدون سررسید")
        layout.addRow("سررسید:", self._due_edit)

        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("توضیحات اختیاری …")
        layout.addRow("توضیحات:", self._desc_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _populate(self, task: Task) -> None:
        self._title_edit.setText(task.title)
        self._desc_edit.setText(task.description)
        idx = self._tag_combo.findText(task.tag)
        if idx >= 0:
            self._tag_combo.setCurrentIndex(idx)
        else:
            self._tag_combo.setCurrentText(task.tag)
        for i in range(self._priority_combo.count()):
            if self._priority_combo.itemData(i) == task.priority:
                self._priority_combo.setCurrentIndex(i)
                break
        self._pomodoro_spin.setValue(task.pomodoros_planned)

    # ── Result ────────────────────────────────────────────────────────────────

    @property
    def title(self) -> str:
        return self._title_edit.text().strip()

    @property
    def description(self) -> str:
        return self._desc_edit.text().strip()

    @property
    def tag(self) -> str:
        return self._tag_combo.currentText().strip()

    @property
    def priority(self) -> TaskPriority:
        return self._priority_combo.currentData()

    @property
    def pomodoros_planned(self) -> int:
        return self._pomodoro_spin.value()

    @property
    def due_date(self) -> Optional[str]:
        date = self._due_edit.date()
        if date.isNull():
            return None
        return date.toString(Qt.DateFormat.ISODate)

    def accept(self) -> None:
        if not self.title:
            self._title_edit.setFocus()
            return
        super().accept()


# ─────────────────────────────────────────────────────────────────────────────
# Task list item
# ─────────────────────────────────────────────────────────────────────────────

class _TaskItem(QListWidgetItem):
    """Custom list item that holds a Task object."""

    def __init__(self, task: Task) -> None:
        super().__init__()
        self.task = task
        self._refresh_text()

    def _refresh_text(self) -> None:
        parts = []
        if self.task.tag:
            parts.append(f"[{self.task.tag}]")
        parts.append(self.task.title)
        parts.append(f"  {self.task.progress_text} 🍅")
        self.setText(" ".join(parts))
        color = _PRIORITY_COLORS.get(self.task.priority, "#9E9E9E")
        self.setForeground(QColor(color if not self.task.is_done else "#555770"))
        if self.task.is_done:
            font = self.font()
            font.setStrikeOut(True)
            self.setFont(font)


# ─────────────────────────────────────────────────────────────────────────────
# TaskWidget
# ─────────────────────────────────────────────────────────────────────────────

class TaskWidget(QWidget):
    """
    Full to-do panel.

    Signals:
        task_selected(int)   — task id selected for the timer
        tasks_changed()      — any CRUD operation completed
    """

    task_selected = Signal(int)
    tasks_changed = Signal()

    def __init__(self, task_manager: TaskManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manager = task_manager
        self._setup_ui()
        self.refresh()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Top bar
        top = QHBoxLayout()
        title = QLabel("وظایف")
        title.setObjectName("sectionTitle")
        top.addWidget(title)
        top.addStretch()

        add_btn = QPushButton("+ جدید")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._add_task)
        top.addWidget(add_btn)
        root.addLayout(top)

        # Search + filter
        filter_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("جستجو …")
        self._search.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._search, stretch=1)

        self._tag_filter = QComboBox()
        self._tag_filter.addItem("همه برچسب‌ها")
        self._tag_filter.currentTextChanged.connect(self._apply_filter)
        filter_row.addWidget(self._tag_filter)
        root.addLayout(filter_row)

        # List
        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.itemDoubleClicked.connect(self._edit_selected)
        self._list.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self._list, stretch=1)

        # Bottom bar
        bottom = QHBoxLayout()
        done_btn = QPushButton("✓ انجام شد")
        done_btn.clicked.connect(self._mark_done)
        edit_btn = QPushButton("✎ ویرایش")
        edit_btn.clicked.connect(self._edit_selected)
        del_btn = QPushButton("🗑 حذف")
        del_btn.setProperty("role", "danger")
        del_btn.clicked.connect(self._delete_selected)

        select_btn = QPushButton("▶ انتخاب برای تایمر")
        select_btn.setObjectName("primaryBtn")
        select_btn.clicked.connect(self._select_for_timer)

        bottom.addWidget(done_btn)
        bottom.addWidget(edit_btn)
        bottom.addWidget(del_btn)
        bottom.addStretch()
        bottom.addWidget(select_btn)
        root.addLayout(bottom)

    # ── Data ──────────────────────────────────────────────────────────────────

    @Slot()
    def refresh(self) -> None:
        """Reload all tasks from the database."""
        self._list.clear()
        tasks = self._manager.get_tasks(status=TaskStatus.PENDING)
        for task in tasks:
            self._list.addItem(_TaskItem(task))

        # Refresh tag filter
        current_tag = self._tag_filter.currentText()
        self._tag_filter.blockSignals(True)
        self._tag_filter.clear()
        self._tag_filter.addItem("همه برچسب‌ها")
        for tag in self._manager.get_tags():
            self._tag_filter.addItem(tag)
        idx = self._tag_filter.findText(current_tag)
        if idx >= 0:
            self._tag_filter.setCurrentIndex(idx)
        self._tag_filter.blockSignals(False)

        self._apply_filter()
        self.tasks_changed.emit()

    def _apply_filter(self) -> None:
        query = self._search.text().lower()
        tag = self._tag_filter.currentText()
        if tag == "همه برچسب‌ها":
            tag = ""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not isinstance(item, _TaskItem):
                continue
            text_match = query in item.task.title.lower() or query in item.task.tag.lower()
            tag_match = not tag or item.task.tag == tag
            item.setHidden(not (text_match and tag_match))

    # ── CRUD handlers ─────────────────────────────────────────────────────────

    @Slot()
    def _add_task(self) -> None:
        dlg = TaskDialog(self, existing_tags=self._manager.get_tags())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._manager.create_task(
                title=dlg.title,
                description=dlg.description,
                tag=dlg.tag,
                priority=dlg.priority,
                due_date=dlg.due_date,
                pomodoros_planned=dlg.pomodoros_planned,
            )
            self.refresh()

    @Slot()
    def _edit_selected(self, item: Optional[QListWidgetItem] = None) -> None:
        item = item or self._list.currentItem()
        if not isinstance(item, _TaskItem):
            return
        dlg = TaskDialog(self, task=item.task, existing_tags=self._manager.get_tags())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._manager.update_task(
                item.task.id,
                title=dlg.title,
                description=dlg.description,
                tag=dlg.tag,
                priority=dlg.priority,
                due_date=dlg.due_date,
                pomodoros_planned=dlg.pomodoros_planned,
            )
            self.refresh()

    @Slot()
    def _mark_done(self) -> None:
        item = self._list.currentItem()
        if isinstance(item, _TaskItem):
            self._manager.mark_done(item.task.id)
            self.refresh()

    @Slot()
    def _delete_selected(self) -> None:
        item = self._list.currentItem()
        if isinstance(item, _TaskItem):
            self._manager.delete_task(item.task.id)
            self.refresh()

    @Slot()
    def _select_for_timer(self) -> None:
        item = self._list.currentItem()
        if isinstance(item, _TaskItem):
            self.task_selected.emit(item.task.id)

    @Slot(QListWidgetItem)
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        pass   # Reserved for future single-click behaviour

    def get_pending_tasks(self) -> list[Task]:
        return self._manager.get_tasks(status=TaskStatus.PENDING)
