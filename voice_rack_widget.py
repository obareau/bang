"""BANG! Voice Rack — scrollable list of per-voice pattern editors.

This is the heart of the interactive editing surface. Each voice (a
`(note, dna, vtype)` tuple, exactly what `pattern_lib.build_voices()` returns)
gets one `VoiceRowWidget` containing:

  - a colored name badge (via `pattern_lib.voice_label`), Mute/Solo/Lock toggles
  - a `DNAGridWidget` (dna_grid_widget.py) for the clickable step pattern
  - transform buttons: Regen 🎲 / Rotate ⟲ / Reverse ⇄ / Double ×2 / Halve ½ / Invert ⇕
  - a density slider (0-100 → 0.0-1.0)
  - a chord-type combo (only for melodic voices: markov / bl / ksp*)
  - a MIDI channel spinbox (0-15) with an "Auto" checkbox (emits -1)

None of the buttons mutate the pattern themselves — they only emit signals
carrying the voice index. The actual mutation logic lives in a separate
`BangSession`-like object (built by another agent) that connects to the rack's
bubbled-up signals. This module deliberately has NO dependency on that object.

`VoiceRackWidget` wraps everything in a QScrollArea and re-emits every child
row signal with the same signature, so an external listener connects once to
the rack instead of once per row.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QSpinBox, QCheckBox, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, Signal

from dna_grid_widget import DNAGridWidget
import pattern_lib


# ---------------------------------------------------------------------------
# Shared styling helpers (dark slate / brass palette, matching the rest of the app)
# ---------------------------------------------------------------------------

_TOGGLE_QSS = """
QPushButton {
    background: #202836; color: #7a8494;
    border: 1px solid #2b3446; border-radius: 3px;
    padding: 2px 6px; font-size: 11px; font-weight: bold;
}
QPushButton:hover { background: #2b3446; color: #ddd6cc; }
QPushButton:checked { background: %(on)s; color: #0a0e14; border-color: %(on)s; }
"""

_XFORM_QSS = """
QPushButton {
    background: #1a2135; color: #ddd6cc;
    border: 1px solid #2b3446; border-radius: 3px;
    padding: 2px 6px; font-size: 12px;
}
QPushButton:hover { background: #b8956a; color: #0a0e14; border-color: #b8956a; }
QPushButton:pressed { background: #d4b896; }
"""

_SLIDER_QSS = """
QSlider::groove:horizontal { background: #202836; height: 4px; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #b8956a; width: 12px; margin: -4px 0; border-radius: 2px;
}
QSlider::handle:horizontal:hover { background: #d4b896; }
"""

_COMBO_QSS = """
QComboBox {
    background: #141a26; color: #ddd6cc;
    border: 1px solid #202836; border-radius: 3px;
    padding: 2px 6px; font-size: 11px;
}
QComboBox:hover { border-color: #b8956a; }
QComboBox QAbstractItemView {
    background: #141a26; color: #ddd6cc; selection-background-color: #b8956a;
}
"""

_SPIN_QSS = """
QSpinBox {
    background: #141a26; color: #ddd6cc;
    border: 1px solid #202836; border-radius: 3px;
    padding: 1px 4px; font-size: 11px;
}
QSpinBox:hover { border-color: #b8956a; }
"""

_NEUTRAL_BADGE = "#7a8494"


def _badge_color(note: int, vtype: str) -> str:
    """Pick a badge color for a voice from pattern_lib color tables."""
    try:
        if vtype.startswith("vfm"):
            return pattern_lib.VFM_PART_COLORS[int(vtype[3:])]
        if vtype.startswith("vd"):
            return pattern_lib.VD_PART_COLORS[int(vtype[2:])]
        if vtype.startswith("mf"):
            return pattern_lib.MF_PART_COLORS[int(vtype[2:])]
        if vtype.startswith("ksp"):
            return pattern_lib.KSP_TRACK_COLORS[min(int(vtype[3:]) - 1, 3)]
    except (ValueError, IndexError):
        return _NEUTRAL_BADGE
    return pattern_lib.NOTE_COLOR.get(note, _NEUTRAL_BADGE)


def _wants_chord(vtype: str) -> bool:
    """Chords only make sense for melodic voices."""
    return vtype in ("markov", "bl") or vtype.startswith("ksp")


# ---------------------------------------------------------------------------
# One row per voice
# ---------------------------------------------------------------------------

class VoiceRowWidget(QWidget):
    """A single voice: name/toggles header + DNA grid + transforms + controls."""

    # All signals carry the voice index as the first argument.
    regen_requested = Signal(int)
    rotate_requested = Signal(int)
    reverse_requested = Signal(int)
    double_requested = Signal(int)
    halve_requested = Signal(int)
    invert_requested = Signal(int)

    mute_toggled = Signal(int, bool)
    solo_toggled = Signal(int, bool)
    lock_toggled = Signal(int, bool)

    dna_edited = Signal(int, str)          # (idx, new_dna) — from the grid
    density_changed = Signal(int, int)     # (idx, 0-100)
    chord_changed = Signal(int, str)       # (idx, chord_name)
    midi_channel_changed = Signal(int, int)  # (idx, channel) — channel == -1 means Auto

    def __init__(self, idx: int, note: int, dna: str, vtype: str, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.note = note
        self.vtype = vtype

        self.setObjectName("voiceRow")
        self.setStyleSheet(
            "#voiceRow { background: #141a26; border: 1px solid #202836; border-radius: 5px; }"
        )
        self._build_ui(note, dna, vtype)

    # -- construction ------------------------------------------------------

    def _build_ui(self, note: int, dna: str, vtype: str) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(5)

        # --- Header row: badge + mute/solo/lock ---
        header = QHBoxLayout()
        header.setSpacing(6)

        color = _badge_color(note, vtype)
        self.badge = QLabel(pattern_lib.voice_label(note, vtype))
        self.badge.setStyleSheet(
            f"background: {color}; color: #0a0e14; font-weight: bold; "
            f"font-size: 11px; padding: 2px 10px; border-radius: 3px;"
        )
        header.addWidget(self.badge)

        self.type_label = QLabel(vtype)
        self.type_label.setStyleSheet("color: #7a8494; font-size: 10px;")
        header.addWidget(self.type_label)

        header.addStretch()

        self.mute_btn = self._toggle("M", "#c98a9e", "Mute this voice")
        self.mute_btn.toggled.connect(lambda on: self.mute_toggled.emit(self.idx, on))
        header.addWidget(self.mute_btn)

        self.solo_btn = self._toggle("S", "#e0a458", "Solo this voice")
        self.solo_btn.toggled.connect(lambda on: self.solo_toggled.emit(self.idx, on))
        header.addWidget(self.solo_btn)

        self.lock_btn = self._toggle("🔓", "#5ec7c2", "Lock: protect from regenerate-all")
        self.lock_btn.toggled.connect(self._on_lock)
        header.addWidget(self.lock_btn)

        outer.addLayout(header)

        # --- DNA grid — its own horizontal-only scroll area, decoupled from
        # the row chrome (badge/mute/solo/lock stay put; only the step grid
        # scrolls when the pattern is longer than the visible width). ---
        self.grid = DNAGridWidget(dna)
        self.grid.dna_changed.connect(lambda s: self.dna_edited.emit(self.idx, s))

        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(False)
        self.grid_scroll.setFixedHeight(DNAGridWidget.CELL_H + 12)
        self.grid_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.grid_scroll.setStyleSheet(
            "QScrollArea { background: #141a26; border: none; }"
        )
        self.grid_scroll.setWidget(self.grid)
        self.grid.resize(self.grid.sizeHint())
        outer.addWidget(self.grid_scroll)

        # --- Controls row: transforms + density + chord + channel ---
        controls = QHBoxLayout()
        controls.setSpacing(4)

        for text, tip, sig in (
            ("🎲", "Regenerate this voice", self.regen_requested),
            ("⟲", "Rotate left by 1", self.rotate_requested),
            ("⇄", "Reverse", self.reverse_requested),
            ("×2", "Double length", self.double_requested),
            ("½", "Halve length", self.halve_requested),
            ("⇕", "Invert hits/silences", self.invert_requested),
        ):
            controls.addWidget(self._xform(text, tip, sig))

        controls.addWidget(self._vsep())

        # Density slider
        dens_lbl = QLabel("Dens")
        dens_lbl.setStyleSheet("color: #7a8494; font-size: 10px;")
        controls.addWidget(dens_lbl)
        self.density = QSlider(Qt.Horizontal)
        self.density.setRange(0, 100)
        self.density.setValue(50)
        self.density.setFixedWidth(80)
        self.density.setStyleSheet(_SLIDER_QSS)
        self.density.valueChanged.connect(lambda v: self.density_changed.emit(self.idx, v))
        controls.addWidget(self.density)

        # Chord combo — only for melodic voices (parented so it never floats
        # as a stray top-level window when it isn't added to the layout).
        self.chord = QComboBox(self)
        self.chord.addItems(sorted(pattern_lib.VALID_CHORDS))
        self.chord.setStyleSheet(_COMBO_QSS)
        self.chord.currentTextChanged.connect(
            lambda t: self.chord_changed.emit(self.idx, t)
        )
        if _wants_chord(vtype):
            controls.addWidget(self._vsep())
            chord_lbl = QLabel("Chord")
            chord_lbl.setStyleSheet("color: #7a8494; font-size: 10px;")
            controls.addWidget(chord_lbl)
            controls.addWidget(self.chord)
        else:
            self.chord.hide()

        controls.addStretch()

        # MIDI channel: Auto checkbox + spinbox
        self.auto_chk = QCheckBox("Auto ch")
        self.auto_chk.setChecked(True)
        self.auto_chk.setStyleSheet("color: #7a8494; font-size: 10px;")
        self.auto_chk.toggled.connect(self._on_auto_toggled)
        controls.addWidget(self.auto_chk)

        self.channel = QSpinBox()
        self.channel.setRange(0, 15)
        self.channel.setValue(0)
        self.channel.setEnabled(False)  # disabled while Auto is on
        self.channel.setStyleSheet(_SPIN_QSS)
        self.channel.valueChanged.connect(self._on_channel_changed)
        controls.addWidget(self.channel)

        outer.addLayout(controls)

    # -- small factory helpers --------------------------------------------

    def _toggle(self, text: str, on_color: str, tip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setToolTip(tip)
        btn.setFixedWidth(30)
        btn.setStyleSheet(_TOGGLE_QSS % {"on": on_color})
        return btn

    def _xform(self, text: str, tip: str, signal: Signal) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tip)
        btn.setFixedWidth(34)
        btn.setStyleSheet(_XFORM_QSS)
        btn.clicked.connect(lambda: signal.emit(self.idx))
        return btn

    def _vsep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #202836;")
        return sep

    # -- internal slots ----------------------------------------------------

    def _on_lock(self, on: bool) -> None:
        self.lock_btn.setText("🔒" if on else "🔓")
        self.lock_toggled.emit(self.idx, on)

    def _on_auto_toggled(self, auto: bool) -> None:
        self.channel.setEnabled(not auto)
        self.midi_channel_changed.emit(self.idx, -1 if auto else self.channel.value())

    def _on_channel_changed(self, value: int) -> None:
        if not self.auto_chk.isChecked():
            self.midi_channel_changed.emit(self.idx, value)

    # -- public API --------------------------------------------------------

    def set_dna(self, dna: str) -> None:
        """Update the grid without emitting dna_edited."""
        self.grid.set_dna(dna)
        self.grid.resize(self.grid.sizeHint())

    def set_playhead(self, step: int) -> None:
        self.grid.set_playhead(step)


# ---------------------------------------------------------------------------
# Scrollable container of voice rows
# ---------------------------------------------------------------------------

class VoiceRackWidget(QWidget):
    """Scrollable list of VoiceRowWidgets. Bubbles up every child row signal."""

    # Re-emitted with the same signatures as VoiceRowWidget.
    regen_requested = Signal(int)
    rotate_requested = Signal(int)
    reverse_requested = Signal(int)
    double_requested = Signal(int)
    halve_requested = Signal(int)
    invert_requested = Signal(int)

    mute_toggled = Signal(int, bool)
    solo_toggled = Signal(int, bool)
    lock_toggled = Signal(int, bool)

    dna_edited = Signal(int, str)
    density_changed = Signal(int, int)
    chord_changed = Signal(int, str)
    midi_channel_changed = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[VoiceRowWidget] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet("QScrollArea { background: #0a0e14; border: none; }")

        self._container = QWidget()
        self._container.setStyleSheet("background: #0a0e14;")
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(6, 6, 6, 6)
        self._vbox.setSpacing(6)
        self._vbox.addStretch()  # keeps rows top-aligned

        self.scroll.setWidget(self._container)
        outer.addWidget(self.scroll)

    # -- population --------------------------------------------------------

    def set_voices(self, voices: list[tuple[int, str, str]]) -> None:
        """Clear and rebuild all rows from (note, dna, vtype) tuples."""
        self.clear()
        for idx, (note, dna, vtype) in enumerate(voices):
            row = VoiceRowWidget(idx, note, dna, vtype)
            self._wire(row)
            # insert before the trailing stretch
            self._vbox.insertWidget(self._vbox.count() - 1, row)
            self._rows.append(row)

    def clear(self) -> None:
        for row in self._rows:
            self._vbox.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

    def update_voice_dna(self, idx: int, dna: str) -> None:
        """Update one row's grid without rebuilding the whole rack."""
        if 0 <= idx < len(self._rows):
            self._rows[idx].set_dna(dna)

    def set_playhead(self, step: int) -> None:
        """Forward the current step to every row's grid."""
        for row in self._rows:
            row.set_playhead(step)

    def rows(self) -> list[VoiceRowWidget]:
        return list(self._rows)

    # -- signal bubbling ---------------------------------------------------

    def _wire(self, row: VoiceRowWidget) -> None:
        row.regen_requested.connect(self.regen_requested)
        row.rotate_requested.connect(self.rotate_requested)
        row.reverse_requested.connect(self.reverse_requested)
        row.double_requested.connect(self.double_requested)
        row.halve_requested.connect(self.halve_requested)
        row.invert_requested.connect(self.invert_requested)
        row.mute_toggled.connect(self.mute_toggled)
        row.solo_toggled.connect(self.solo_toggled)
        row.lock_toggled.connect(self.lock_toggled)
        row.dna_edited.connect(self.dna_edited)
        row.density_changed.connect(self.density_changed)
        row.chord_changed.connect(self.chord_changed)
        row.midi_channel_changed.connect(self.midi_channel_changed)


# ---------------------------------------------------------------------------
# Smoke test — build a rack, exercise the conditional chord logic, run briefly.
# Run headless with:  QT_QPA_PLATFORM=offscreen uv run python voice_rack_widget.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    app = QApplication(sys.argv)

    rack = VoiceRackWidget()
    rack.setStyleSheet("background: #0a0e14;")
    rack.resize(760, 600)

    fake_voices = [
        (36, "x---x---x---x---", "drum"),      # kick, no chord combo
        (38, "----x-------x---", "drum"),      # snare, no chord combo
        (42, "x-x-x-x-x-x-x-x-", "drum"),      # hats, no chord combo
        (33, "x-?-░-↺-x-?-░-↺-", "markov"),   # melodic — chord combo shown
        (33, "x-------x-------", "bl"),         # bassline — chord combo shown
        (60, "x-?-x---x-?-x---", "vd0"),        # volca drum part 0
    ]
    rack.set_voices(fake_voices)

    # Connect one external listener to prove the rack bubbles everything up.
    rack.dna_edited.connect(lambda i, s: print(f"[rack] dna_edited voice={i} dna={s}"))
    rack.regen_requested.connect(lambda i: print(f"[rack] regen voice={i}"))
    rack.chord_changed.connect(lambda i, c: print(f"[rack] chord voice={i} = {c}"))
    rack.midi_channel_changed.connect(lambda i, c: print(f"[rack] channel voice={i} = {c}"))

    # Exercise the visual playhead hook and single-voice DNA update.
    rack.set_playhead(4)
    rack.update_voice_dna(0, "░░░░x---x---x---")

    rack.show()

    # Auto-quit so the headless run terminates cleanly.
    QTimer.singleShot(1500, app.quit)
    print("VoiceRackWidget smoke test: constructed", len(rack.rows()), "rows OK")
    sys.exit(app.exec())
