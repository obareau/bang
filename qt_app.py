"""BANG! Qt6 Native App — PySide6 desktop application."""
import sys
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QComboBox, QSlider, QTabWidget,
    QTableWidget, QTableWidgetItem, QGridLayout, QGroupBox, QStatusBar
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from bang_engine import BangEngine
from pianoroll import PianorollWidget
from midi_routing import MIDIRoutingWidget
from osc_debugger import OSCDebuggerWidget
from nts1_panel import NTS1PanelWidget


class BANGQt(QMainWindow):
    """Main BANG! Qt6 application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BANG! — Algorithmic MIDI Generator v1.0-qt6")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize engine
        self.engine = BangEngine()
        self.bpm = self.engine.bpm
        self.playing = False

        # UI
        self.init_ui()
        self.setup_connections()
        self.setup_timers()

    def init_ui(self):
        """Build UI layout."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout()
        central.setLayout(main_layout)

        # Left panel: Control
        left_panel = self.create_control_panel()
        main_layout.addWidget(left_panel, 1)

        # Right panel: Status + Pianoroll preview
        right_panel = self.create_status_panel()
        main_layout.addWidget(right_panel, 2)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready — engine idle")

    def create_control_panel(self):
        """Left control panel (synth selection, parameters)."""
        group = QGroupBox("Controls")
        layout = QVBoxLayout()

        # Synth selector
        layout.addWidget(QLabel("Synth Mode:"))
        self.synth_combo = QComboBox()
        self.synth_combo.addItems(["TR-808", "NTS-1", "Microfreak", "Generic"])
        layout.addWidget(self.synth_combo)

        # BPM
        layout.addWidget(QLabel("BPM:"))
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(40, 240)
        self.bpm_spin.setValue(120)
        layout.addWidget(self.bpm_spin)

        # Play/Stop
        play_layout = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.stop_btn = QPushButton("⏹ Stop")
        play_layout.addWidget(self.play_btn)
        play_layout.addWidget(self.stop_btn)
        layout.addLayout(play_layout)

        # Randomize
        self.random_btn = QPushButton("🎲 Randomize Pattern")
        layout.addWidget(self.random_btn)

        # NTS-1 panel (shown when NTS-1 selected)
        layout.addWidget(QLabel(""))  # Spacer
        self.nts1_panel = NTS1PanelWidget(self.engine)
        self.nts1_panel.setVisible(False)
        layout.addWidget(self.nts1_panel)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def create_status_panel(self):
        """Right status panel (preview + stats)."""
        tabs = QTabWidget()

        # Stats tab
        stats_widget = QWidget()
        stats_layout = QVBoxLayout()
        self.stats_label = QLabel("Engine Status:\nIdle")
        self.stats_label.setFont(QFont("Courier", 10))
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        stats_widget.setLayout(stats_layout)
        tabs.addTab(stats_widget, "Status")

        # Pianoroll tab
        self.pianoroll = PianorollWidget(self.engine)
        tabs.addTab(self.pianoroll, "Pianoroll")

        # MIDI Routing tab
        self.midi_routing = MIDIRoutingWidget(self.engine)
        tabs.addTab(self.midi_routing, "🔌 MIDI")

        # OSC Debugger tab
        self.osc_debugger = OSCDebuggerWidget(self.engine)
        self.osc_debugger.log_example_messages()  # Demo messages
        tabs.addTab(self.osc_debugger, "🔍 OSC")

        return tabs

    def setup_connections(self):
        """Wire UI buttons to engine."""
        self.play_btn.clicked.connect(self.on_play)
        self.stop_btn.clicked.connect(self.on_stop)
        self.random_btn.clicked.connect(self.on_randomize)
        self.synth_combo.currentTextChanged.connect(self.on_synth_changed)
        self.bpm_spin.valueChanged.connect(self.on_bpm_changed)

    def setup_timers(self):
        """Setup UI refresh timer."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(500)  # Update every 500ms

    def on_play(self):
        """Play current sequence."""
        self.playing = True
        self.engine.playing = True
        self.status_bar.showMessage("▶ Playing...")

    def on_stop(self):
        """Stop playback."""
        self.playing = False
        self.engine.playing = False
        self.status_bar.showMessage("⏹ Stopped")

    def on_randomize(self):
        """Generate random pattern."""
        self.engine.randomize()
        self.status_bar.showMessage("🎲 Randomized")

    def on_synth_changed(self, synth_name):
        """Handle synth mode change."""
        print(f"Synth changed to: {synth_name}")
        self.status_bar.showMessage(f"Synth: {synth_name}")

        # Show/hide NTS-1 panel based on selection
        self.nts1_panel.setVisible(synth_name == "NTS-1")

    def on_bpm_changed(self, bpm):
        """Handle BPM change."""
        self.engine.bpm = bpm
        self.status_bar.showMessage(f"BPM: {bpm}")

    def update_status(self):
        """Update status display from engine."""
        status_text = f"""Engine Status:
Running: {self.playing}
BPM: {self.engine.bpm}
Voices: {len(self.engine.voices)}
Mode: {self.synth_combo.currentText()}"""
        self.stats_label.setText(status_text)


def main():
    """Entry point for Qt6 app."""
    app = QApplication(sys.argv)
    window = BANGQt()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
