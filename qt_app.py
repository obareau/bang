"""BANG! Qt6 Native App — PySide6 desktop application.

Main window wiring: GeneratorPanel (mode/chaos/bpm/scale) drives a
BangSession (bang_session.py), which owns the real pattern-generation logic
(pattern_lib.py — ported from the production webapp, web.py). VoiceRackWidget
is the primary interactive editing surface (click-to-cycle DNA grids +
per-voice transforms). LiveClock (live_clock.py) is a real-time MIDI thread
behind Play/Stop, polled by a QTimer to drive the playhead highlight.
"""
import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QGroupBox, QStatusBar, QSplitter,
    QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

import mido

from bang_session import BangSession
from live_clock import LiveClock
from generator_panel import GeneratorPanel
from voice_rack_widget import VoiceRackWidget
from pianoroll import PianorollWidget
from midi_routing import MIDIRoutingWidget
from osc_debugger import OSCDebuggerWidget
from nts1_panel import NTS1PanelWidget
from microfreak_panel import MicrofreaklockPanelWidget


class BANGQt(QMainWindow):
    """Main BANG! Qt6 application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BANG! — Algorithmic MIDI Generator v2.0-qt6")
        self.setGeometry(100, 100, 1500, 900)
        self.setStyleSheet("QMainWindow { background: #0a0e14; }")

        self.session = BangSession()
        self.live_clock: LiveClock | None = None

        self.init_ui()
        self.setup_connections()
        self.setup_timers()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left: generator controls + transport
        left = self.create_left_panel()
        splitter.addWidget(left)

        # Center: voice rack (the main editing surface)
        self.voice_rack = VoiceRackWidget()
        splitter.addWidget(self.voice_rack)

        # Right: secondary tabs (pianoroll preview, synth panels, MIDI/OSC)
        right = self.create_right_panel()
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        splitter.setCollapsible(1, False)
        splitter.setSizes([320, 860, 320])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready — no pattern generated yet")

    def create_left_panel(self):
        container = QWidget()
        layout = QVBoxLayout(container)

        self.generator_panel = GeneratorPanel()
        layout.addWidget(self.generator_panel)

        transport_group = QGroupBox("Transport")
        transport_group.setStyleSheet("QGroupBox { color: #b8956a; font-weight: bold; }")
        t_layout = QVBoxLayout()
        transport_group.setLayout(t_layout)

        play_row = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play (MIDI out)")
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setEnabled(False)
        play_row.addWidget(self.play_btn)
        play_row.addWidget(self.stop_btn)
        t_layout.addLayout(play_row)

        self.preview_btn = QPushButton("🔊 Preview (built-in synth)")
        self.preview_btn.setStyleSheet(
            "QPushButton { background: #5ec7c2; color: #0a0e14; font-weight: bold; padding: 6px; }"
        )
        t_layout.addWidget(self.preview_btn)

        layout.addWidget(transport_group)

        return container

    def create_right_panel(self):
        tabs = QTabWidget()

        # Stats tab
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        self.stats_label = QLabel("Engine Status:\nIdle")
        self.stats_label.setFont(QFont("Courier", 10))
        self.stats_label.setStyleSheet("color: #ddd6cc;")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        tabs.addTab(stats_widget, "Status")

        # Pianoroll preview (read-only, driven directly by the session — auto
        # reflects whatever session.voices/last_p are at any given time)
        self.pianoroll = PianorollWidget(self.session)
        tabs.addTab(self.pianoroll, "Pianoroll")

        # MIDI Routing tab (port selection feeds LiveClock)
        self.midi_routing = MIDIRoutingWidget(self.session.engine)
        tabs.addTab(self.midi_routing, "🔌 MIDI")

        # OSC Debugger tab
        self.osc_debugger = OSCDebuggerWidget(self.session.engine)
        tabs.addTab(self.osc_debugger, "🔍 OSC")

        # NTS-1 / Microfreak synth panels (per-voice CC p-lock lanes)
        self.nts1_panel = NTS1PanelWidget(self.session.engine)
        tabs.addTab(self.nts1_panel, "NTS-1")

        self.microfreak_panel = MicrofreaklockPanelWidget(self.session.engine)
        tabs.addTab(self.microfreak_panel, "Microfreak")

        return tabs

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def setup_connections(self):
        self.generator_panel.generate_requested.connect(self.on_generate)
        self.generator_panel.export_requested.connect(self.on_export)
        self.generator_panel.vary_all_requested.connect(self.on_vary_all)
        self.generator_panel.undo_requested.connect(self.on_undo)

        self.voice_rack.regen_requested.connect(self.on_voice_regen)
        self.voice_rack.rotate_requested.connect(lambda idx: self.on_voice_transform(idx, "rotate"))
        self.voice_rack.reverse_requested.connect(lambda idx: self.on_voice_transform(idx, "reverse"))
        self.voice_rack.double_requested.connect(lambda idx: self.on_voice_transform(idx, "double"))
        self.voice_rack.halve_requested.connect(lambda idx: self.on_voice_transform(idx, "halve"))
        self.voice_rack.invert_requested.connect(lambda idx: self.on_voice_transform(idx, "invert"))
        self.voice_rack.lock_toggled.connect(lambda idx, on: self.session.set_lock(idx, on))
        self.voice_rack.dna_edited.connect(self.on_dna_edited)
        self.voice_rack.density_changed.connect(self.on_density_changed)
        self.voice_rack.chord_changed.connect(self.on_chord_changed)
        self.voice_rack.midi_channel_changed.connect(self.on_midi_channel_changed)

        self.play_btn.clicked.connect(self.on_play)
        self.preview_btn.clicked.connect(self.on_preview)
        self.stop_btn.clicked.connect(self.on_stop)

    def setup_timers(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(200)

    # ------------------------------------------------------------------
    # Generator actions
    # ------------------------------------------------------------------

    def on_generate(self, params: dict):
        gen_params = {k: v for k, v in params.items() if k != "midi_type"}
        self.session.generate(**gen_params)
        self.voice_rack.set_voices(self.session.voices)
        self.midi_routing.engine = self.session.engine
        n = len(self.session.voices)
        self.status_bar.showMessage(f"Generated {n} voices — mode={params['mode']} bpm={params['bpm']}")

    def on_export(self, params: dict):
        if not self.session.last_p:
            self.on_generate(params)

        default_name = params.get("out") or "bang_out.mid"
        from pathlib import Path
        default_dir = str(Path(__file__).parent / "exports")
        chosen, _ = QFileDialog.getSaveFileName(
            self, "Exporter le MIDI", str(Path(default_dir) / default_name),
            "Fichiers MIDI (*.mid)"
        )
        if not chosen:
            return  # annulé

        chosen_path = Path(chosen)
        try:
            path = self.session.export_midi(
                filename=chosen_path.name, dest_dir=str(chosen_path.parent),
                midi_type=params.get("midi_type", 1),
            )
            self.status_bar.showMessage(f"Exported: {path}")
            QMessageBox.information(self, "Export réussi", f"Fichier MIDI exporté :\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def on_vary_all(self):
        self.session.vary_all()
        self.voice_rack.set_voices(self.session.voices)
        self.status_bar.showMessage("Varied all unlocked voices")

    def on_undo(self):
        if self.session.undo():
            self.voice_rack.set_voices(self.session.voices)
            self.status_bar.showMessage("Undo")
        else:
            self.status_bar.showMessage("Nothing to undo")

    # ------------------------------------------------------------------
    # Voice rack actions
    # ------------------------------------------------------------------

    def on_voice_regen(self, idx: int):
        if self.session.regen_voice(idx):
            self.voice_rack.update_voice_dna(idx, self.session.voices[idx][1])

    def on_voice_transform(self, idx: int, kind: str):
        method = {
            "rotate": lambda: self.session.rotate_voice(idx, 1),
            "reverse": lambda: self.session.reverse_voice(idx),
            "double": lambda: self.session.double_voice(idx),
            "halve": lambda: self.session.halve_voice(idx),
            "invert": lambda: self.session.invert_voice(idx),
        }[kind]
        if method():
            self.voice_rack.update_voice_dna(idx, self.session.voices[idx][1])

    def on_dna_edited(self, idx: int, dna: str):
        self.session.set_voice_pattern(idx, dna)

    def _voice_name(self, idx: int) -> str | None:
        if not (0 <= idx < len(self.session.voices)):
            return None
        import pattern_lib as pl
        note, _dna, vtype = self.session.voices[idx]
        return pl.voice_label(note, vtype)

    def on_density_changed(self, idx: int, value: int):
        name = self._voice_name(idx)
        if name:
            self.session.set_voice_density(name, value / 100)

    def on_chord_changed(self, idx: int, chord: str):
        name = self._voice_name(idx)
        if name:
            self.session.set_voice_chord(name, chord)

    def on_midi_channel_changed(self, idx: int, channel: int):
        name = self._voice_name(idx)
        if name:
            self.session.set_voice_midi_channel(name, channel)

    # ------------------------------------------------------------------
    # Transport (real MIDI clock)
    # ------------------------------------------------------------------

    def on_play(self):
        """Play out to a real/virtual MIDI port (external synth/DAW/hardware)."""
        if not self.session.last_p:
            self.status_bar.showMessage("Generate a pattern first")
            return

        port_name = self.midi_routing.selected_port()
        ports = mido.get_output_names()
        if port_name not in ports:
            if not ports:
                QMessageBox.warning(self, "No MIDI port", "No MIDI output port available on this system.")
                return
            port_name = ports[0]

        self.live_clock = LiveClock(self.session, port_name=port_name)
        try:
            self.live_clock.start()
        except Exception as e:
            QMessageBox.warning(self, "MIDI error", str(e))
            self.live_clock = None
            return

        self.play_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_bar.showMessage(f"▶ Playing on {port_name}")

    def on_preview(self):
        """Play through the built-in FluidSynth preview — no external MIDI needed."""
        if not self.session.last_p:
            self.status_bar.showMessage("Generate a pattern first")
            return

        self.live_clock = LiveClock(self.session, use_preview_synth=True)
        try:
            self.live_clock.start()
        except Exception as e:
            QMessageBox.warning(
                self, "Preview synth error",
                f"{e}\n\nInstall a GM soundfont, e.g.:\nsudo apt install fluid-soundfont-gm"
            )
            self.live_clock = None
            return

        self.play_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_bar.showMessage("🔊 Previewing (built-in synth)")

    def on_stop(self):
        if self.live_clock:
            self.live_clock.stop()
            self.live_clock = None
        self.voice_rack.set_playhead(-1)
        self.play_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_bar.showMessage("⏹ Stopped")

    # ------------------------------------------------------------------
    # Status refresh / playhead
    # ------------------------------------------------------------------

    def update_status(self):
        n_voices = len(self.session.voices)
        bpm = self.session.last_p["bpm"] if self.session.last_p else "—"
        mode = self.session.last_p["mode"] if self.session.last_p else "—"
        playing = self.live_clock is not None and self.live_clock.is_running
        status_text = (
            f"Engine Status:\n"
            f"Running: {playing}\n"
            f"BPM: {bpm}\n"
            f"Mode: {mode}\n"
            f"Voices: {n_voices}\n"
            f"Locked: {sorted(self.session.locked_voices)}"
        )
        self.stats_label.setText(status_text)

        if playing:
            self.voice_rack.set_playhead(self.live_clock.current_step)

    def closeEvent(self, event):
        if self.live_clock:
            self.live_clock.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = BANGQt()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
