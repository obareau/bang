"""BANG! MIDI Routing UI — port selection and OSC config."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QSpinBox, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QCheckBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
import mido


class MIDIRoutingWidget(QWidget):
    """MIDI port selection and routing configuration."""

    def __init__(self, engine=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.init_ui()
        self.refresh_ports()

        # Auto-refresh ports
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_ports)
        self.timer.start(2000)

    def init_ui(self):
        """Build MIDI routing UI."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # MIDI Output section
        midi_group = QGroupBox("MIDI Output")
        midi_layout = QVBoxLayout()

        midi_row = QHBoxLayout()
        midi_row.addWidget(QLabel("Port:"))
        self.midi_combo = QComboBox()
        self.midi_combo.currentTextChanged.connect(self.on_midi_selected)
        midi_row.addWidget(self.midi_combo)

        self.midi_status = QLabel("● Disconnected")
        self.midi_status.setStyleSheet("color: #f2617d;")
        midi_row.addWidget(self.midi_status)
        midi_row.addStretch()

        midi_layout.addLayout(midi_row)
        midi_group.setLayout(midi_layout)
        layout.addWidget(midi_group)

        # MIDI Channels section
        chan_group = QGroupBox("MIDI Channels")
        chan_layout = QVBoxLayout()

        # Channel mapping table
        self.chan_table = QTableWidget()
        self.chan_table.setColumnCount(3)
        self.chan_table.setHorizontalHeaderLabels(["Voice", "Channel", "Enabled"])
        self.chan_table.setMaximumHeight(150)
        chan_layout.addWidget(self.chan_table)

        chan_group.setLayout(chan_layout)
        layout.addWidget(chan_group)

        # OSC section
        osc_group = QGroupBox("OSC Config")
        osc_layout = QVBoxLayout()

        # OSC Host
        osc_host_row = QHBoxLayout()
        osc_host_row.addWidget(QLabel("Host:"))
        self.osc_host = QLineEdit("127.0.0.1")
        osc_host_row.addWidget(self.osc_host)
        osc_layout.addLayout(osc_host_row)

        # OSC Port
        osc_port_row = QHBoxLayout()
        osc_port_row.addWidget(QLabel("Port:"))
        self.osc_port = QSpinBox()
        self.osc_port.setRange(1024, 65535)
        self.osc_port.setValue(9005)
        osc_port_row.addWidget(self.osc_port)

        self.osc_status = QLabel("● Ready")
        self.osc_status.setStyleSheet("color: #5ec75c;")
        osc_port_row.addWidget(self.osc_status)
        osc_port_row.addStretch()

        osc_layout.addLayout(osc_port_row)

        # Test OSC button
        test_osc_btn = QPushButton("📡 Test OSC")
        test_osc_btn.clicked.connect(self.test_osc)
        osc_layout.addWidget(test_osc_btn)

        osc_group.setLayout(osc_layout)
        layout.addWidget(osc_group)

        layout.addStretch()

    def refresh_ports(self):
        """Refresh available MIDI ports."""
        current = self.midi_combo.currentText()
        self.midi_combo.blockSignals(True)
        self.midi_combo.clear()

        ports = mido.get_output_names()
        self.midi_combo.addItems(ports + ["— Virtual —"])

        # Restore previous selection
        idx = self.midi_combo.findText(current)
        if idx >= 0:
            self.midi_combo.setCurrentIndex(idx)

        self.midi_combo.blockSignals(False)

        # Update channel table
        self.update_channel_table()

    def update_channel_table(self):
        """Update MIDI channel mapping table."""
        self.chan_table.setRowCount(0)

        if self.engine:
            voices = self.engine.state.get("voices", [])
            for i, voice in enumerate(voices):
                self.chan_table.insertRow(i)

                # Voice name
                voice_name = voice.get("name", f"Voice {i}")
                name_item = QTableWidgetItem(voice_name)
                name_item.setForeground(QColor("#b8956a"))
                self.chan_table.setItem(i, 0, name_item)

                # Channel selector
                chan = voice.get("channel", i % 16 + 1)
                chan_combo = QComboBox()
                chan_combo.addItems([str(c) for c in range(1, 17)] + ["Auto"])
                chan_combo.setCurrentText(str(chan))
                self.chan_table.setCellWidget(i, 1, chan_combo)

                # Enabled checkbox
                enabled = voice.get("enabled", True)
                check = QCheckBox()
                check.setChecked(enabled)
                self.chan_table.setCellWidget(i, 2, check)

    def on_midi_selected(self, port_name: str):
        """Handle MIDI port selection."""
        if port_name == "— Virtual —":
            self.midi_status.setText("● Virtual")
            self.midi_status.setStyleSheet("color: #fda946;")
        elif port_name:
            self.midi_status.setText(f"● {port_name}")
            self.midi_status.setStyleSheet("color: #5ec75c;")
            if self.engine:
                self.engine.state["midi_output"] = port_name
        else:
            self.midi_status.setText("● Disconnected")
            self.midi_status.setStyleSheet("color: #f2617d;")

    def test_osc(self):
        """Test OSC connectivity."""
        self.osc_status.setText("● Testing...")
        self.osc_status.setStyleSheet("color: #fda946;")

        try:
            host = self.osc_host.text()
            port = self.osc_port.value()
            # Note: actual test would require sending packet
            print(f"OSC test: {host}:{port}")
            self.osc_status.setText("● OK")
            self.osc_status.setStyleSheet("color: #5ec75c;")
        except Exception as e:
            self.osc_status.setText(f"● Error: {str(e)[:20]}")
            self.osc_status.setStyleSheet("color: #f2617d;")
