"""BANG! NTS-1 Panel — real-time parameter control."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QSpinBox, QGroupBox, QGridLayout, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor


class NTS1PanelWidget(QWidget):
    """NTS-1 synthesizer parameter panel with p-lock visualization."""

    # Signals for parameter changes
    param_changed = Signal(str, int)  # (cc_name, value)

    # NTS-1 p-lock CC map (from roadmap)
    PLOCK_PROFILE = {
        "cutoff": (43, "Cutoff"),
        "oscshp": (53, "OscShp"),
        "oscalt": (54, "OscAlt"),
        "lfoint": (25, "LFOInt"),
        "reso": (44, "Reso"),
        "revmix": (38, "RevMix"),
    }

    def __init__(self, engine=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.current_step = 0
        self.p_locks = {}  # {step: {param: value}}
        self.init_ui()

    def init_ui(self):
        """Build NTS-1 6-section panel."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Title
        title = QLabel("🎛️ Korg NTS-1 mk1 Panel")
        title.setStyleSheet("color: #b8956a; font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Grid: 2 columns × 3 rows
        grid = QGridLayout()
        grid.setSpacing(10)

        # OSC section (top-left)
        grid.addWidget(self.create_osc_section(), 0, 0)

        # FILTER section (top-right)
        grid.addWidget(self.create_filter_section(), 0, 1)

        # LFO section (mid-left)
        grid.addWidget(self.create_lfo_section(), 1, 0)

        # EG section (mid-right)
        grid.addWidget(self.create_eg_section(), 1, 1)

        # FX section (bottom-left)
        grid.addWidget(self.create_fx_section(), 2, 0)

        # P-lock section (bottom-right)
        grid.addWidget(self.create_plock_section(), 2, 1)

        layout.addLayout(grid)
        layout.addStretch()

    def create_slider(self, label: str, cc: int, min_val=0, max_val=127):
        """Create labeled slider."""
        group = QGroupBox(label)
        glay = QVBoxLayout()

        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
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
        slider.valueChanged.connect(lambda v: self.param_changed.emit(f"cc{cc}", v))
        glay.addWidget(slider)

        value_label = QLabel("64")
        value_label.setStyleSheet("color: #b8956a; text-align: center; font-size: 11px;")
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        glay.addWidget(value_label)

        group.setLayout(glay)
        return group, slider

    def create_osc_section(self):
        """OSC: Shape, Alt."""
        group = QGroupBox("OSC")
        layout = QVBoxLayout()

        self.osc_shape, self.osc_shape_slider = self.create_slider("Shape", 53, 0, 127)
        layout.addWidget(self.osc_shape)

        self.osc_alt, self.osc_alt_slider = self.create_slider("Alt", 54, 0, 127)
        layout.addWidget(self.osc_alt)

        group.setLayout(layout)
        return group

    def create_filter_section(self):
        """FILTER: Cutoff, Reso, Type."""
        group = QGroupBox("FILTER")
        layout = QVBoxLayout()

        self.filt_cutoff, self.filt_cutoff_slider = self.create_slider("Cutoff", 43, 0, 127)
        layout.addWidget(self.filt_cutoff)

        self.filt_reso, self.filt_reso_slider = self.create_slider("Reso", 44, 0, 127)
        layout.addWidget(self.filt_reso)

        # Filter type (simplified: 0-127 maps to types)
        self.filt_type, self.filt_type_slider = self.create_slider("Type", 20, 0, 127)
        layout.addWidget(self.filt_type)

        group.setLayout(layout)
        return group

    def create_lfo_section(self):
        """LFO: Rate, Intensity, Type."""
        group = QGroupBox("LFO")
        layout = QVBoxLayout()

        self.lfo_rate, self.lfo_rate_slider = self.create_slider("Rate", 76, 0, 127)
        layout.addWidget(self.lfo_rate)

        self.lfo_int, self.lfo_int_slider = self.create_slider("Int", 25, 0, 127)
        layout.addWidget(self.lfo_int)

        self.lfo_type, self.lfo_type_slider = self.create_slider("Type", 21, 0, 3)
        layout.addWidget(self.lfo_type)

        group.setLayout(layout)
        return group

    def create_eg_section(self):
        """EG: Attack, Release."""
        group = QGroupBox("EG")
        layout = QVBoxLayout()

        self.eg_atk, self.eg_atk_slider = self.create_slider("Attack", 73, 0, 127)
        layout.addWidget(self.eg_atk)

        self.eg_rel, self.eg_rel_slider = self.create_slider("Release", 72, 0, 127)
        layout.addWidget(self.eg_rel)

        group.setLayout(layout)
        return group

    def create_fx_section(self):
        """FX: Delay, Reverb."""
        group = QGroupBox("FX")
        layout = QVBoxLayout()

        self.fx_delay, self.fx_delay_slider = self.create_slider("Delay", 22, 0, 127)
        layout.addWidget(self.fx_delay)

        self.fx_reverb, self.fx_reverb_slider = self.create_slider("Reverb", 38, 0, 127)
        layout.addWidget(self.fx_reverb)

        group.setLayout(layout)
        return group

    def create_plock_section(self):
        """P-lock control and visualization."""
        group = QGroupBox("P-locks")
        layout = QVBoxLayout()

        # P-lock enable
        self.plock_enable = QCheckBox("Enable P-locks")
        self.plock_enable.setChecked(False)
        self.plock_enable.setStyleSheet("color: #ddd6cc;")
        layout.addWidget(self.plock_enable)

        # P-lock interpolation mode
        interp_layout = QHBoxLayout()
        interp_layout.addWidget(QLabel("Interpolation:"))
        self.interp_combo = self.create_combo(["off", "linear", "cosine"])
        interp_layout.addWidget(self.interp_combo)
        layout.addLayout(interp_layout)

        # P-lock randomizer
        random_layout = QHBoxLayout()
        self.random_btn = self.create_button("🎲 Randomize")
        random_layout.addWidget(self.random_btn)
        layout.addLayout(random_layout)

        # P-lock status
        self.plock_status = QLabel("No p-locks on this step")
        self.plock_status.setStyleSheet("color: #7a8494; font-size: 10px;")
        layout.addWidget(self.plock_status)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def create_combo(self, items):
        """Create styled combo."""
        from PySide6.QtWidgets import QComboBox
        combo = QComboBox()
        combo.addItems(items)
        combo.setStyleSheet("""
            QComboBox {
                background: #141a26;
                color: #ddd6cc;
                border: 1px solid #202836;
                padding: 2px;
                font-size: 11px;
            }
        """)
        return combo

    def create_button(self, text):
        """Create styled button."""
        from PySide6.QtWidgets import QPushButton
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background: #b8956a;
                color: #000;
                border: none;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background: #d4b896;
            }
        """)
        return btn

    def set_current_step(self, step: int):
        """Update p-lock status for current step."""
        self.current_step = step
        if step in self.p_locks:
            locks = self.p_locks[step]
            status = f"Step {step}: {len(locks)} p-locks"
        else:
            status = f"Step {step}: No p-locks"
        self.plock_status.setText(status)
