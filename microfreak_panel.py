"""BANG! Microfreak Panel — Arturia Microfreak synthesizer support."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QSlider, QLabel, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from p_locks import PLockSequence


class MicrofreaklockSequence(PLockSequence):
    """Microfreak-specific p-lock profile."""

    # CC confirmés par Arturia pour le MicroFreak. Les anciens numéros
    # (Timbre 28, Cutoff 74, Reso 71, LFO 76/77, EG 73/72) venaient du MiniFreak
    # ou étaient inventés ; LFO et enveloppe sont retirés tant que leurs CC
    # ne sont pas vérifiés dans le manuel.
    MICROFREAK_PROFILE = {
        "type": (9, "Type", 0, 127),           # CC9 : type d'oscillateur
        "wave": (10, "Wave", 0, 127),          # CC10 : paramètre Wave
        "timbre": (12, "Timbre", 0, 127),      # CC12 : paramètre Timbre
        "shape": (13, "Shape", 0, 127),        # CC13 : paramètre Shape
        "cutoff": (23, "Cutoff", 0, 127),      # CC23 : coupure filtre
        "reso": (83, "Resonance", 0, 127),     # CC83 : résonance filtre
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

        type_group, self.type_slider = self.create_slider("Type", 9)
        osc_layout.addWidget(type_group)

        wave_group, self.wave_slider = self.create_slider("Wave", 10)
        osc_layout.addWidget(wave_group)

        timbre_group, self.timbre_slider = self.create_slider("Timbre", 12)
        osc_layout.addWidget(timbre_group)

        shape_group, self.shape_slider = self.create_slider("Shape", 13)
        osc_layout.addWidget(shape_group)

        osc_group.setLayout(osc_layout)
        layout.addWidget(osc_group)

        # Filter section
        filt_group = QGroupBox("Filter")
        filt_layout = QVBoxLayout()

        cutoff_group, self.cutoff_slider = self.create_slider("Cutoff", 23)
        filt_layout.addWidget(cutoff_group)

        reso_group, self.reso_slider = self.create_slider("Resonance", 83)
        filt_layout.addWidget(reso_group)

        filt_group.setLayout(filt_layout)
        layout.addWidget(filt_group)

        # LFO / Envelope : retirés — CC MicroFreak non confirmés (voir ROADMAP).

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
