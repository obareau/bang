"""BANG! MIDI Activity Monitor — real-time "what's sounding right now" view.

A compact, poll-based activity monitor for the live MIDI engine (live_clock.py),
styled like a hardware synth's channel activity LEDs plus a scrolling note-on
log. Designed to live as one tab in the main window's right-side QTabWidget.

The widget does NOT hold a fixed reference to a LiveClock: the main window
creates a fresh LiveClock every time Play/Preview is pressed, so this widget is
handed a zero-arg *getter* (`live_clock_getter`) that returns the CURRENT
`LiveClock | None`. An internal QTimer polls it ~12x/second:

  - `LiveClock.active_notes()` -> {(channel, note): voice_name}  drives the LEDs
  - `LiveClock.recent_events()` -> [(ts, ch, note, vel, name), ...]  drives the log

When the getter returns None (nothing playing), it shows an "Idle" state and all
LEDs go dim — no crash, no busy-looping on a dead clock.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont


# Palette — cohesive with the rest of the app (dark slate / brass).
_LED_ON = "#b8956a"      # brass — channel has an active note
_LED_ON_ALT = "#5ec75c"  # bright green — alternate lit color
_LED_OFF = "#202836"     # dim slate — channel idle
_LED_TEXT_ON = "#0a0e14"
_LED_TEXT_OFF = "#4a5464"

_N_CHANNELS = 16
_POLL_MS = 80
_LOG_MAX = 50


class MIDIActivityWidget(QWidget):
    """Live MIDI activity monitor: 16 channel LEDs + scrolling note-on log.

    Args:
        live_clock_getter: zero-arg callable returning the current
            `LiveClock | None`. Polled every ~80ms; None => Idle.
    """

    def __init__(self, live_clock_getter: Callable[[], object | None], parent=None):
        super().__init__(parent)
        self._get_clock = live_clock_getter
        # High-water mark: only log note-on events newer than this timestamp.
        self._last_logged_ts = 0.0

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(_POLL_MS)

    # -- construction ------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Status line
        self.status = QLabel("Idle")
        self.status.setStyleSheet("color: #7a8494; font-size: 11px; font-weight: bold;")
        outer.addWidget(self.status)

        # Channel LED strip (16 channels, MIDI ch 1-16).
        leds = QHBoxLayout()
        leds.setSpacing(3)
        self._leds: list[QLabel] = []
        for ch in range(_N_CHANNELS):
            led = QLabel(str(ch + 1))
            led.setAlignment(Qt.AlignCenter)
            led.setFixedSize(20, 20)
            led.setToolTip(f"MIDI channel {ch + 1} — idle")
            self._leds.append(led)
            leds.addWidget(led)
        leds.addStretch()
        outer.addLayout(leds)
        self._paint_leds(set(), {})

        # Scrolling note-on log (read-only, monospace, dark).
        self.log = QListWidget()
        self.log.setStyleSheet(
            "QListWidget { background: #0a0e14; color: #ddd6cc; border: 1px solid #202836; "
            "border-radius: 4px; }"
            "QListWidget::item { padding: 0px 2px; }"
        )
        self.log.setFont(QFont("Menlo", 9))
        self.log.setSelectionMode(QListWidget.NoSelection)
        self.log.setFocusPolicy(Qt.NoFocus)
        outer.addWidget(self.log)

    # -- LED painting ------------------------------------------------------

    def _paint_leds(self, active_channels: set[int],
                    tips: dict[int, list[str]]) -> None:
        for ch, led in enumerate(self._leds):
            on = ch in active_channels
            bg = _LED_ON if on else _LED_OFF
            fg = _LED_TEXT_ON if on else _LED_TEXT_OFF
            led.setStyleSheet(
                f"background: {bg}; color: {fg}; border-radius: 3px; "
                f"font-size: 10px; font-weight: bold;"
            )
            if on and tips.get(ch):
                led.setToolTip(f"ch{ch + 1}: " + ", ".join(tips[ch]))
            else:
                led.setToolTip(f"MIDI channel {ch + 1} — idle")

    # -- polling -----------------------------------------------------------

    def _poll(self) -> None:
        clock = None
        try:
            clock = self._get_clock()
        except Exception:
            clock = None

        if clock is None or not getattr(clock, "is_running", False):
            self.status.setText("Idle")
            self._paint_leds(set(), {})
            return

        # Active notes -> which channels are lit + tooltip content.
        try:
            active = clock.active_notes()
        except Exception:
            active = {}
        active_channels: set[int] = set()
        tips: dict[int, list[str]] = {}
        for (ch, note), name in active.items():
            active_channels.add(ch)
            tips.setdefault(ch, []).append(f"{name} n{note}")

        self.status.setText(
            f"Playing — {len(active)} note(s) on {len(active_channels)} channel(s)"
        )
        self._paint_leds(active_channels, tips)

        # Append new note-on events to the log.
        try:
            events = clock.recent_events()
        except Exception:
            events = []
        new = [e for e in events if e[0] > self._last_logged_ts]
        for ts, ch, note, vel, name in new:
            self._append_log(ts, ch, note, vel, name)
            self._last_logged_ts = max(self._last_logged_ts, ts)

    def _append_log(self, ts: float, ch: int, note: int, vel: int, name: str) -> None:
        stamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
        line = f"{stamp}  ch{ch + 1:<2}  {name:<10}  note={note:<3}  vel={vel}"
        item = QListWidgetItem(line)
        item.setForeground(QColor("#b8956a"))
        self.log.addItem(item)
        # Trim to the last _LOG_MAX lines.
        while self.log.count() > _LOG_MAX:
            self.log.takeItem(0)
        self.log.scrollToBottom()


# ---------------------------------------------------------------------------
# Smoke test — construct with a getter returning None, confirm the "Idle" state
# renders without crashing. Run headless with:
#   QT_QPA_PLATFORM=offscreen uv run python midi_activity_widget.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Getter returns None => Idle state, no LiveClock present.
    w = MIDIActivityWidget(lambda: None)
    w.resize(520, 320)
    w.show()

    # Force one poll cycle synchronously and assert Idle.
    w._poll()
    assert w.status.text() == "Idle", f"expected Idle, got {w.status.text()!r}"
    assert len(w._leds) == 16, "expected 16 channel LEDs"

    QTimer.singleShot(500, app.quit)
    print("MIDIActivityWidget smoke test: Idle state OK, 16 LEDs constructed")
    sys.exit(app.exec())
