"""
ui/audio_panel.py
Ambient sound mixer panel: one channel card per sound with volume slider.
"""

from __future__ import annotations
import logging

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSlider, QVBoxLayout, QWidget,
)

from media.audio_mixer import AudioMixer

logger = logging.getLogger(__name__)

# Icon mapping for each channel (emoji fallback)
_CHANNEL_ICONS = {
    "rain":       "🌧",
    "fireplace":  "🔥",
    "cafe":       "☕",
    "keyboard":   "⌨",
    "whitenoise": "🌊",
}


# ─────────────────────────────────────────────────────────────────────────────
# Single channel control card
# ─────────────────────────────────────────────────────────────────────────────

class _ChannelCard(QWidget):
    """Volume card for one ambient sound channel."""

    volume_changed = Signal(str, float)   # name, volume

    def __init__(self, name: str, initial_volume: float = 0.5, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("channelCard")
        self._name = name
        self._muted = False
        self._setup_ui(initial_volume)

    def _setup_ui(self, volume: float) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Icon + name
        icon = _CHANNEL_ICONS.get(self._name, "🎵")
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 24px;")
        layout.addWidget(icon_label)

        name_label = QLabel(self._name.capitalize())
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setObjectName("statCaption")
        layout.addWidget(name_label)

        # Vertical slider
        self._slider = QSlider(Qt.Orientation.Vertical)
        self._slider.setRange(0, 100)
        self._slider.setValue(int(volume * 100))
        self._slider.setFixedHeight(100)
        self._slider.valueChanged.connect(self._on_slider)
        layout.addWidget(self._slider, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Volume value label
        self._vol_label = QLabel(f"{int(volume * 100)}%")
        self._vol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vol_label.setObjectName("statCaption")
        layout.addWidget(self._vol_label)

        # Mute toggle
        self._mute_btn = QPushButton("🔇")
        self._mute_btn.setObjectName("iconBtn")
        self._mute_btn.setToolTip("قطع/وصل صدا")
        self._mute_btn.clicked.connect(self._on_mute)
        layout.addWidget(self._mute_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

    @Slot(int)
    def _on_slider(self, value: int) -> None:
        self._vol_label.setText(f"{value}%")
        if not self._muted:
            self.volume_changed.emit(self._name, value / 100.0)

    @Slot()
    def _on_mute(self) -> None:
        self._muted = not self._muted
        self._mute_btn.setText("🔊" if self._muted else "🔇")
        vol = 0.0 if self._muted else self._slider.value() / 100.0
        self.volume_changed.emit(self._name, vol)

    def set_volume(self, volume: float) -> None:
        self._slider.setValue(int(volume * 100))


# ─────────────────────────────────────────────────────────────────────────────
# AudioPanel
# ─────────────────────────────────────────────────────────────────────────────

class AudioPanel(QWidget):
    """
    Full ambient mixer panel.
    One _ChannelCard per AudioMixer channel.
    """

    def __init__(self, mixer: AudioMixer, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mixer = mixer
        self._cards: dict[str, _ChannelCard] = {}
        self._setup_ui()
        self._populate_channels()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Header
        header = QHBoxLayout()
        title = QLabel("فضاساز صدا")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()

        self._play_all_btn = QPushButton("▶ همه")
        self._play_all_btn.setObjectName("primaryBtn")
        self._play_all_btn.clicked.connect(self._on_play_all)
        header.addWidget(self._play_all_btn)

        stop_all_btn = QPushButton("■ توقف")
        stop_all_btn.clicked.connect(self._on_stop_all)
        header.addWidget(stop_all_btn)
        root.addLayout(header)

        # Scroll area containing channel cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        cards_container = QWidget()
        self._cards_layout = QHBoxLayout(cards_container)
        self._cards_layout.setSpacing(8)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(cards_container)
        root.addWidget(scroll, stretch=1)

        # Preset row
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("پریست:"))
        for preset_name, preset_data in self._default_presets().items():
            btn = QPushButton(preset_name)
            btn.clicked.connect(lambda checked, d=preset_data: self._apply_preset(d))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        root.addLayout(preset_row)

    def _populate_channels(self) -> None:
        for name in self._mixer.channel_names():
            vol = self._mixer.get_volume(name)
            card = _ChannelCard(name, vol)
            card.volume_changed.connect(self._on_volume_changed)
            self._cards[name] = card
            self._cards_layout.addWidget(card)

    # ── Slots ─────────────────────────────────────────────────────────────────

    @Slot(str, float)
    def _on_volume_changed(self, name: str, volume: float) -> None:
        self._mixer.set_volume(name, volume)
        if volume > 0:
            self._mixer.play_channel(name)
        else:
            self._mixer.stop_channel(name)

    @Slot()
    def _on_play_all(self) -> None:
        self._mixer.play_all()
        self._play_all_btn.setText("■ در حال پخش")

    @Slot()
    def _on_stop_all(self) -> None:
        self._mixer.stop_all()
        self._play_all_btn.setText("▶ همه")

    def _apply_preset(self, preset: dict[str, float]) -> None:
        self._mixer.restore_state(preset)
        for name, vol in preset.items():
            if name in self._cards:
                self._cards[name].set_volume(vol)
        self._mixer.play_all()

    # ── Public API ────────────────────────────────────────────────────────────

    def sync_from_mixer(self) -> None:
        """Re-read volumes from the mixer (e.g. after restore_state)."""
        for name, card in self._cards.items():
            card.set_volume(self._mixer.get_volume(name))

    @staticmethod
    def _default_presets() -> dict[str, dict[str, float]]:
        return {
            "کتابخانه": {"rain": 0.0, "fireplace": 0.0, "cafe": 0.3, "keyboard": 0.5, "whitenoise": 0.2},
            "جنگل بارانی": {"rain": 0.7, "fireplace": 0.0, "cafe": 0.0, "keyboard": 0.0, "whitenoise": 0.3},
            "شومینه": {"rain": 0.0, "fireplace": 0.8, "cafe": 0.0, "keyboard": 0.0, "whitenoise": 0.0},
        }
