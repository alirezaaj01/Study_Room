"""
media/audio_mixer.py
Multi-channel ambient audio mixer using PySide6 QtMultimedia.
Each sound (rain, fire, café …) runs in its own QMediaPlayer.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Channel
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AmbientChannel:
    """A single playback channel for one ambient sound."""
    name:       str
    file_path:  str
    player:     QMediaPlayer    = field(repr=False, default=None)   # type: ignore
    audio_out:  QAudioOutput    = field(repr=False, default=None)   # type: ignore
    volume:     float           = 0.5   # 0.0 – 1.0
    muted:      bool            = False

    def effective_volume(self) -> float:
        return 0.0 if self.muted else self.volume


# ─────────────────────────────────────────────────────────────────────────────
# Mixer
# ─────────────────────────────────────────────────────────────────────────────

class AudioMixer:
    """
    Manages N AmbientChannels.
    Must be created *after* QApplication exists (Qt requirement).
    """

    # Built-in channel definitions: (name, asset_filename)
    DEFAULT_CHANNELS: list[tuple[str, str]] = [
        ("rain",       "rain.mp3"),
        ("fireplace",  "fireplace.mp3"),
        ("cafe",       "cafe.mp3"),
        ("keyboard",   "keyboard.mp3"),
        ("whitenoise", "whitenoise.mp3"),
    ]

    def __init__(self, assets_dir: Optional[str] = None) -> None:
        self._channels: dict[str, AmbientChannel] = {}
        self._assets_dir: Path = Path(assets_dir) if assets_dir else Path("assets/sounds")

    # ── Setup ─────────────────────────────────────────────────────────────────

    def load_default_channels(self) -> None:
        """Load all built-in channels if their asset files exist."""
        for name, filename in self.DEFAULT_CHANNELS:
            path = self._assets_dir / filename
            self.load_channel(name, str(path))

    def load_channel(self, name: str, file_path: str) -> AmbientChannel:
        """Create (or replace) a channel. Returns the new AmbientChannel."""
        # Clean up existing channel if any
        if name in self._channels:
            self._stop_player(self._channels[name])

        audio_out = QAudioOutput()
        player = QMediaPlayer()
        player.setAudioOutput(audio_out)

        if Path(file_path).exists():
            player.setSource(QUrl.fromLocalFile(file_path))
            player.setLoops(QMediaPlayer.Loops.Infinite)
        else:
            logger.warning("Audio file not found: %s", file_path)

        ch = AmbientChannel(
            name=name,
            file_path=file_path,
            player=player,
            audio_out=audio_out,
        )
        audio_out.setVolume(ch.effective_volume())
        self._channels[name] = ch
        logger.debug("Loaded channel: %s", name)
        return ch

    # ── Playback control ──────────────────────────────────────────────────────

    def play_channel(self, name: str) -> None:
        ch = self._channels.get(name)
        if ch and ch.player:
            ch.player.play()

    def stop_channel(self, name: str) -> None:
        ch = self._channels.get(name)
        if ch:
            self._stop_player(ch)

    def play_all(self) -> None:
        for name in self._channels:
            self.play_channel(name)

    def stop_all(self) -> None:
        for ch in self._channels.values():
            self._stop_player(ch)

    # ── Volume control ────────────────────────────────────────────────────────

    def set_volume(self, name: str, volume: float) -> None:
        """Set volume 0.0–1.0 for a named channel."""
        ch = self._channels.get(name)
        if ch is None:
            return
        ch.volume = max(0.0, min(1.0, volume))
        if ch.audio_out:
            ch.audio_out.setVolume(ch.effective_volume())

    def set_muted(self, name: str, muted: bool) -> None:
        ch = self._channels.get(name)
        if ch and ch.audio_out:
            ch.muted = muted
            ch.audio_out.setVolume(ch.effective_volume())

    def toggle_mute(self, name: str) -> bool:
        """Toggle mute state, return new muted value."""
        ch = self._channels.get(name)
        if ch is None:
            return False
        self.set_muted(name, not ch.muted)
        return ch.muted

    def get_volume(self, name: str) -> float:
        ch = self._channels.get(name)
        return ch.volume if ch else 0.0

    # ── Presets / Persistence ─────────────────────────────────────────────────

    def get_state(self) -> dict[str, float]:
        """Return {name: volume} for all channels. Used to persist to settings."""
        return {name: ch.volume for name, ch in self._channels.items()}

    def restore_state(self, state: dict[str, float]) -> None:
        """Restore volumes from a previously saved state dict."""
        for name, volume in state.items():
            if name in self._channels:
                self.set_volume(name, volume)

    # ── Channels access ───────────────────────────────────────────────────────

    def get_channel(self, name: str) -> Optional[AmbientChannel]:
        return self._channels.get(name)

    def channel_names(self) -> list[str]:
        return list(self._channels.keys())

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _stop_player(ch: AmbientChannel) -> None:
        try:
            if ch.player:
                ch.player.stop()
        except Exception as exc:
            logger.debug("Error stopping player for %s: %s", ch.name, exc)

    def cleanup(self) -> None:
        """Stop all playback. Call on application exit."""
        self.stop_all()
        self._channels.clear()
