"""BANG! Microfreak Panel — Arturia Microfreak synthesizer support."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QSlider, QLabel, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from p_locks import PLockSequence


class MicrofreaklockSequence(PLockSequence):
    """Microfreak-specific p-lock profile."""

    MICROFREAK_PROFILE = {
        "timbre": (28, "Timbre", 0, 127),      # CC28: oscillator shape
        "wave": (9, "Wave", 0, 127),           # CC9: waveform select
        "cutoff": (74, "Cutoff", 0, 127),     # CC74: filter cutoff
        "reso": (71, "Resonance", 0, 127),    # CC71: filter resonance
        "lfo_rate": (76, "LFO Rate", 0, 127), # CC76: LFO speed
        "lfo_amt": (77, "LFO Amt", 0, 127),   # CC77: LFO amount
        "eg_atk": (73, "Attack", 0, 127),     # CC73: envelope attack
        "eg_rel": (72, "Release", 0, 127),    # CC72: envelope release
    }

    def __init__(self):
        # Don't call parent init, use Microfreak profile instead
        self.profile = "microfreak"
        self.tracks = {}
        self.pattern_length = 16

        for name, (cc, label, min_v, max_v) in self.MICROFREAK_PROFILE.items():
            from p_locks import PLockTrack
            self.tracks[name] = PLockTrack(cc, label, min_v, max_v)


class MicrofreaklockPanelWidget(QWidget):
    """Microfreak synth parameter panel."""

    def __init__(self, engine=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.plock_seq = MicrofreaklockSequence()
        self.init_ui()

    def init_ui(self):
        """Build Microfreak panel."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Title
        title = QLabel("🎛️ Arturia Microfreak Panel")
        title.setStyleSheet("color: #b8956a; font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Oscillator section
        osc_group = QGroupBox("Oscillator")
        osc_layout = QVBoxLayout()

        timbre_group, self.timbre_slider = self.create_slider("Timbre", 28)
        osc_layout.addWidget(timbre_group)

        wave_group, self.wave_slider = self.create_slider("Wave", 9)
        osc_layout.addWidget(wave_group)

        osc_group.setLayout(osc_layout)
        layout.addWidget(osc_group)

        # Filter section
        filt_group = QGroupBox("Filter")
        filt_layout = QVBoxLayout()

        cutoff_group, self.cutoff_slider = self.create_slider("Cutoff", 74)
        filt_layout.addWidget(cutoff_group)

        reso_group, self.reso_slider = self.create_slider("Resonance", 71)
        filt_layout.addWidget(reso_group)

        filt_group.setLayout(filt_layout)
        layout.addWidget(filt_group)

        # LFO section
        lfo_group = QGroupBox("LFO")
        lfo_layout = QVBoxLayout()

        rate_group, self.lfo_rate_slider = self.create_slider("Rate", 76)
        lfo_layout.addWidget(rate_group)

        amt_group, self.lfo_amt_slider = self.create_slider("Amount", 77)
        lfo_layout.addWidget(amt_group)

        lfo_group.setLayout(lfo_layout)
        layout.addWidget(lfo_group)

        # Envelope section
        eg_group = QGroupBox("Envelope")
        eg_layout = QVBoxLayout()

        atk_group, self.eg_atk_slider = self.create_slider("Attack", 73)
        eg_layout.addWidget(atk_group)

        rel_group, self.eg_rel_slider = self.create_slider("Release", 72)
        eg_layout.addWidget(rel_group)

        eg_group.setLayout(eg_layout)
        layout.addWidget(eg_group)

        layout.addStretch()

    def create_slider(self, label: str, cc: int):
        """Create labeled slider."""
        group = QGroupBox(label)
        glay = QVBoxLayout()

        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 127)
        slider.setValue(64)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #202836;
                height: 4px;
            }
            QSlider::handle:horizontal {
                background: #b8956a;
                width: 12px;
                margin: -4px 0;
                border-radius: 2px;
            }
        """)
        glay.addWidget(slider)

        value_label = QLabel("64")
        value_label.setStyleSheet("color: #b8956a; text-align: center; font-size: 11px;")
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        glay.addWidget(value_label)

        group.setLayout(glay)
        return group, slider
