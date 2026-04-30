"""
core/pomodoro.py
Pure-Python Pomodoro engine — zero UI/IO dependencies.
Must be driven externally by calling tick() every second.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# State & Config
# ─────────────────────────────────────────────────────────────────────────────

class PomodoroState(Enum):
    IDLE        = auto()
    WORK        = auto()
    SHORT_BREAK = auto()
    LONG_BREAK  = auto()
    PAUSED      = auto()


@dataclass
class PomodoroConfig:
    """All durations are in minutes."""
    work_minutes:           int = 25
    short_break_minutes:    int = 5
    long_break_minutes:     int = 15
    sessions_before_long:   int = 4
    auto_start_breaks:      bool = False
    auto_start_work:        bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────

class PomodoroEngine:
    """
    Stateful Pomodoro timer engine.

    Lifecycle:
        IDLE -> start() -> WORK
        WORK -> tick() * N -> on_complete -> SHORT_BREAK / LONG_BREAK
        ANY  -> pause()  -> PAUSED
        PAUSED -> resume() -> previous state
        ANY  -> stop()   -> IDLE
        ANY  -> skip()   -> next phase
    """

    def __init__(self, config: Optional[PomodoroConfig] = None) -> None:
        self.config: PomodoroConfig = config or PomodoroConfig()

        # State
        self._state: PomodoroState          = PomodoroState.IDLE
        self._state_before_pause: PomodoroState = PomodoroState.IDLE
        self._session_count: int            = 0   # completed WORK sessions
        self._remaining_seconds: int        = 0
        self._total_seconds: int            = 0

        # Callbacks — assign before calling start()
        self.on_tick:           Callable[[PomodoroState, int, int], None] = lambda *a: None
        self.on_phase_change:   Callable[[PomodoroState, int], None]     = lambda *a: None
        self.on_complete:       Callable[[PomodoroState, int], None]     = lambda *a: None

    # ── Public read-only properties ───────────────────────────────────────────

    @property
    def state(self) -> PomodoroState:
        return self._state

    @property
    def session_count(self) -> int:
        return self._session_count

    @property
    def remaining_seconds(self) -> int:
        return self._remaining_seconds

    @property
    def total_seconds(self) -> int:
        return self._total_seconds

    @property
    def is_running(self) -> bool:
        return self._state not in (PomodoroState.IDLE, PomodoroState.PAUSED)

    @property
    def elapsed_seconds(self) -> int:
        return self._total_seconds - self._remaining_seconds

    # ── Control API ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start or resume the engine. If IDLE, begin a WORK phase."""
        if self._state == PomodoroState.PAUSED:
            self.resume()
            return
        if self._state != PomodoroState.IDLE:
            logger.warning("start() called while state=%s — ignored.", self._state)
            return
        self._enter_phase(PomodoroState.WORK)

    def pause(self) -> None:
        """Freeze the timer; remember state for resume()."""
        if self._state in (PomodoroState.IDLE, PomodoroState.PAUSED):
            return
        self._state_before_pause = self._state
        self._state = PomodoroState.PAUSED
        logger.debug("Paused at %ds remaining.", self._remaining_seconds)

    def resume(self) -> None:
        """Continue from where we paused."""
        if self._state != PomodoroState.PAUSED:
            return
        self._state = self._state_before_pause
        logger.debug("Resumed into %s.", self._state)
        self.on_phase_change(self._state, self._session_count)

    def stop(self) -> None:
        """
        Abort current phase and return to IDLE.
        Fires on_complete with completed=False (duration = elapsed).
        """
        if self._state == PomodoroState.IDLE:
            return
        finished_state = (
            self._state_before_pause
            if self._state == PomodoroState.PAUSED
            else self._state
        )
        elapsed = self._total_seconds - self._remaining_seconds
        self.on_complete(finished_state, elapsed)
        self._reset()
        self.on_phase_change(PomodoroState.IDLE, self._session_count)
        logger.debug("Stopped. elapsed=%ds", elapsed)

    def skip(self) -> None:
        """Skip the current phase and move to the next one immediately."""
        if self._state == PomodoroState.IDLE:
            return
        current = (
            self._state_before_pause
            if self._state == PomodoroState.PAUSED
            else self._state
        )
        # Fire on_complete for the skipped phase with 0 duration
        self.on_complete(current, 0)
        next_state = self._next_phase(current)
        self._enter_phase(next_state)

    def tick(self) -> None:
        """
        Must be called exactly once per second by the external driver (e.g. QTimer).
        Does nothing when IDLE or PAUSED.
        """
        if self._state in (PomodoroState.IDLE, PomodoroState.PAUSED):
            return

        self._remaining_seconds -= 1
        self.on_tick(self._state, self._remaining_seconds, self._total_seconds)

        if self._remaining_seconds <= 0:
            self._phase_complete()

    def update_config(self, config: PomodoroConfig) -> None:
        """Update config. Takes effect on the next phase start."""
        self.config = config
        logger.debug("Config updated: %s", config)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _enter_phase(self, phase: PomodoroState) -> None:
        self._state = phase
        self._total_seconds = self._duration_for(phase)
        self._remaining_seconds = self._total_seconds
        logger.debug("Entering phase %s (%ds)", phase, self._total_seconds)
        self.on_phase_change(phase, self._session_count)

    def _phase_complete(self) -> None:
        completed = self._state
        if completed == PomodoroState.WORK:
            self._session_count += 1
        duration = self._total_seconds  # full duration
        # on_complete fires BEFORE on_phase_change (per spec)
        self.on_complete(completed, duration)
        next_phase = self._next_phase(completed)
        self._enter_phase(next_phase)

    def _next_phase(self, current: PomodoroState) -> PomodoroState:
        if current == PomodoroState.WORK:
            if self._session_count % self.config.sessions_before_long == 0:
                return PomodoroState.LONG_BREAK
            return PomodoroState.SHORT_BREAK
        # After any break → WORK
        return PomodoroState.WORK

    def _duration_for(self, phase: PomodoroState) -> int:
        """Return phase duration in seconds."""
        mapping = {
            PomodoroState.WORK:        self.config.work_minutes        * 60,
            PomodoroState.SHORT_BREAK: self.config.short_break_minutes * 60,
            PomodoroState.LONG_BREAK:  self.config.long_break_minutes  * 60,
        }
        return mapping.get(phase, 0)

    def _reset(self) -> None:
        self._state = PomodoroState.IDLE
        self._remaining_seconds = 0
        self._total_seconds = 0
        self._state_before_pause = PomodoroState.IDLE
