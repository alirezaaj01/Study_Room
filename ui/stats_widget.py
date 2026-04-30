"""
ui/stats_widget.py
Analytics dashboard: matplotlib charts embedded in PySide6.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from core.session_tracker import SessionTracker

logger = logging.getLogger(__name__)

# Dark-theme colours for matplotlib
_BG      = "#0F1117"
_CARD_BG = "#1A1D27"
_TEXT    = "#E8EAF6"
_MUTED   = "#9E9E9E"
_ACCENT  = "#6C63FF"
_GREEN   = "#4CAF50"
_ORANGE  = "#FF9800"

_PALETTE = [_ACCENT, _GREEN, _ORANGE, "#F44336", "#00BCD4", "#E91E63", "#9C27B0"]


def _apply_dark_style(ax) -> None:
    ax.set_facecolor(_CARD_BG)
    ax.figure.patch.set_facecolor(_BG)
    ax.tick_params(colors=_MUTED, labelsize=8)
    ax.spines[:].set_color("#2D3245")
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(_MUTED)


# ─────────────────────────────────────────────────────────────────────────────
# StatsWidget
# ─────────────────────────────────────────────────────────────────────────────

class StatsWidget(QWidget):
    """
    Displays study statistics with three charts:
      1. Bar chart: work hours for last 7 days
      2. Pie chart: tag distribution this week
      3. Heatmap: 12-week GitHub-style contribution grid
    Plus summary cards at the top.
    """

    def __init__(self, tracker: SessionTracker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tracker = tracker
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("آمار مطالعه")
        title.setObjectName("sectionTitle")
        header_row.addWidget(title)
        header_row.addStretch()
        refresh_btn = QPushButton("↻ بروزرسانی")
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        root.addLayout(header_row)

        # Summary cards
        self._cards_row = QHBoxLayout()
        self._today_card = self._make_card("امروز", "0 دقیقه")
        self._week_card  = self._make_card("این هفته", "0 ساعت")
        self._streak_card = self._make_card("استریک", "0 روز")
        self._sessions_card = self._make_card("جلسات امروز", "0")
        for card in [self._today_card, self._week_card, self._streak_card, self._sessions_card]:
            self._cards_row.addWidget(card)
        root.addLayout(self._cards_row)

        # Scroll area for charts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        charts_layout = QVBoxLayout(inner)
        charts_layout.setSpacing(16)

        # Chart 1 — daily bar
        self._fig_bar = Figure(figsize=(7, 2.5), tight_layout=True)
        self._canvas_bar = FigureCanvasQTAgg(self._fig_bar)
        self._canvas_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._canvas_bar.setMinimumHeight(200)
        charts_layout.addWidget(QLabel("ساعات مطالعه — ۷ روز اخیر"))
        charts_layout.addWidget(self._canvas_bar)

        # Chart 2 — pie
        self._fig_pie = Figure(figsize=(4, 3), tight_layout=True)
        self._canvas_pie = FigureCanvasQTAgg(self._fig_pie)
        self._canvas_pie.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._canvas_pie.setMinimumHeight(240)
        charts_layout.addWidget(QLabel("توزیع زمان بر اساس برچسب — این هفته"))
        charts_layout.addWidget(self._canvas_pie)

        # Chart 3 — heatmap
        self._fig_heat = Figure(figsize=(7, 2.5), tight_layout=True)
        self._canvas_heat = FigureCanvasQTAgg(self._fig_heat)
        self._canvas_heat.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._canvas_heat.setMinimumHeight(180)
        charts_layout.addWidget(QLabel("نقشه فعالیت — ۱۲ هفته اخیر"))
        charts_layout.addWidget(self._canvas_heat)

        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

    @staticmethod
    def _make_card(caption: str, value: str) -> QWidget:
        card = QWidget()
        card.setObjectName("statsCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        val_label = QLabel(value)
        val_label.setObjectName("statValue")
        val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap_label = QLabel(caption)
        cap_label.setObjectName("statCaption")
        cap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(val_label)
        lay.addWidget(cap_label)
        card.setProperty("_val_label", val_label)
        return card

    @staticmethod
    def _update_card(card: QWidget, value: str) -> None:
        lbl: QLabel = card.property("_val_label")
        if lbl:
            lbl.setText(value)

    # ── Refresh ───────────────────────────────────────────────────────────────

    @Slot()
    def refresh(self) -> None:
        """Reload all data from tracker and redraw charts."""
        self._update_summary_cards()
        self._draw_bar_chart()
        self._draw_pie_chart()
        self._draw_heatmap()

    def _update_summary_cards(self) -> None:
        today = self._tracker.get_daily_stats()
        streak = self._tracker.get_streak()
        weekly = self._tracker.get_weekly_stats()
        week_seconds = sum(d.work_seconds for d in weekly)

        self._update_card(self._today_card,   f"{today.work_minutes} دقیقه")
        self._update_card(self._week_card,    f"{week_seconds // 3600:.1f} ساعت")
        self._update_card(self._streak_card,  f"{streak} روز")
        self._update_card(self._sessions_card, str(today.sessions_count))

    def _draw_bar_chart(self) -> None:
        days = self._tracker.get_last_n_days(7)
        labels = [d.date[-5:] for d in days]   # MM-DD
        minutes = [d.work_minutes for d in days]

        self._fig_bar.clear()
        ax = self._fig_bar.add_subplot(111)
        bars = ax.bar(labels, minutes, color=_ACCENT, alpha=0.85, width=0.5)
        ax.set_ylabel("دقیقه", color=_MUTED, fontsize=8)
        ax.set_title("مطالعه روزانه", color=_TEXT, fontsize=10, pad=8)
        for bar, val in zip(bars, minutes):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 1,
                    str(val),
                    ha="center", va="bottom",
                    fontsize=7, color=_MUTED,
                )
        _apply_dark_style(ax)
        self._canvas_bar.draw()

    def _draw_pie_chart(self) -> None:
        weekly = self._tracker.get_weekly_stats()
        tag_seconds: dict[str, int] = {}
        for day in weekly:
            for tag in day.tasks:
                tag_seconds[tag] = tag_seconds.get(tag, 0) + day.work_seconds

        self._fig_pie.clear()
        ax = self._fig_pie.add_subplot(111)

        if not tag_seconds:
            ax.text(0.5, 0.5, "داده‌ای موجود نیست",
                    ha="center", va="center", color=_MUTED, fontsize=10,
                    transform=ax.transAxes)
            ax.set_visible(True)
        else:
            labels = list(tag_seconds.keys())
            sizes  = [tag_seconds[k] // 60 for k in labels]
            colors = _PALETTE[:len(labels)]
            ax.pie(sizes, labels=labels, colors=colors,
                   autopct="%1.0f%%", textprops={"color": _TEXT, "fontsize": 9},
                   wedgeprops={"linewidth": 1, "edgecolor": _BG})
            ax.set_title("توزیع برچسب‌ها", color=_TEXT, fontsize=10)

        _apply_dark_style(ax)
        ax.set_facecolor(_BG)
        self._canvas_pie.draw()

    def _draw_heatmap(self) -> None:
        data = self._tracker.get_heatmap_data(weeks=12)
        today = datetime.now().date()
        weeks = 12
        total_days = weeks * 7

        grid: list[list[float]] = [[] for _ in range(7)]
        for i in range(total_days - 1, -1, -1):
            date = today - timedelta(days=i)
            day_of_week = date.weekday()   # 0=Mon
            val = data.get(date.strftime("%Y-%m-%d"), 0)
            minutes = val / 60.0
            grid[day_of_week].append(minutes)

        self._fig_heat.clear()
        ax = self._fig_heat.add_subplot(111)

        import numpy as np
        matrix = np.zeros((7, weeks))
        for row_idx, row_data in enumerate(grid):
            for col_idx, val in enumerate(row_data[:weeks]):
                matrix[row_idx, col_idx] = val

        ax.imshow(matrix, cmap="Blues", aspect="auto", interpolation="nearest")
        days_labels = ["دو", "سه", "چهار", "پنج", "جمعه", "شنبه", "یک"]
        ax.set_yticks(range(7))
        ax.set_yticklabels(days_labels, fontsize=7)
        ax.set_xticks([])
        ax.set_title("نقشه فعالیت (دقیقه)", color=_TEXT, fontsize=10)
        _apply_dark_style(ax)
        self._canvas_heat.draw()
