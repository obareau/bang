"""BANG! NTS-1 Panel — real-time parameter control."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QSpinBox, QGroupBox, QGridLayout, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from midi_cc_router import MIDICCRouter
from p_locks import InterpolationMode


class NTS1PanelWidget(QWidget):
    """NTS-1 synthesizer parameter panel with p-lock visualization.

    CC (Korg NTS-1 MIDI implementation chart, 2019) :
      EG type 14 / attack 16 / release 19 · trémolo depth 20 / rate 21
      OSC LFO rate 24 / depth 26 · MOD time 28 / depth 29
      DELAY time 30 / depth 31 / mix 33 · REVERB time 34 / depth 35 / mix 36
      FILTER type 42 / cutoff 43 / resonance 44 · sweep depth 45 / rate 46
      OSC type 53 / shape 54 / alt 55 · MOD type 88 · DELAY type 89 · REVERB type 90
      ARP pattern 117 / intervals 118 / length 119
    """

    # Signals for parameter changes
    param_changed = Signal(str, int)  # (cc_name, value)

    # NTS-1 p-lock CC map — tableau MIDI officiel Korg « NTS-1 digital kit » (2019)
    PLOCK_PROFILE = {
        "cutoff": (43, "Cutoff"),
        "oscshp": (54, "OscShp"),
        "oscalt": (55, "OscAlt"),
        "lfoint": (26, "LFOInt"),
        "reso": (44, "Reso"),
        "revmix": (36, "RevMix"),
    }

    def __init__(self, engine=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.current_step = 0
        self.p_locks = {}  # {step: {param: value}}

        # Initialize MIDI router
        self.router = MIDICCRouter(engine)
        self.router.setup_nts1_plock_seq()

        self.init_ui()
        self.setup_connections()

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

        self.osc_shape, self.osc_shape_slider = self.create_slider("Shape", 54, 0, 127)
        layout.addWidget(self.osc_shape)

        self.osc_alt, self.osc_alt_slider = self.create_slider("Alt", 55, 0, 127)
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
        self.filt_type, self.filt_type_slider = self.create_slider("Type", 42, 0, 127)
        layout.addWidget(self.filt_type)

        group.setLayout(layout)
        return group

    def create_lfo_section(self):
        """OSC LFO: Rate, Depth (le NTS-1 n'a pas de CC de type de LFO)."""
        group = QGroupBox("LFO")
        layout = QVBoxLayout()

        self.lfo_rate, self.lfo_rate_slider = self.create_slider("Rate", 24, 0, 127)
        layout.addWidget(self.lfo_rate)

        self.lfo_int, self.lfo_int_slider = self.create_slider("Int", 26, 0, 127)
        layout.addWidget(self.lfo_int)

        group.setLayout(layout)
        return group

    def create_eg_section(self):
        """EG: Attack, Release."""
        group = QGroupBox("EG")
        layout = QVBoxLayout()

        self.eg_atk, self.eg_atk_slider = self.create_slider("Attack", 16, 0, 127)
        layout.addWidget(self.eg_atk)

        self.eg_rel, self.eg_rel_slider = self.create_slider("Release", 19, 0, 127)
        layout.addWidget(self.eg_rel)

        group.setLayout(layout)
        return group

    def create_fx_section(self):
        """FX: Delay mix (CC33), Reverb mix (CC36)."""
        group = QGroupBox("FX")
        layout = QVBoxLayout()

        self.fx_delay, self.fx_delay_slider = self.create_slider("Delay", 33, 0, 127)
        layout.addWidget(self.fx_delay)

        self.fx_reverb, self.fx_reverb_slider = self.create_slider("Reverb", 36, 0, 127)
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

    def setup_connections(self):
        """Connect panel sliders to MIDI router."""
        # OSC
        self.osc_shape_slider.valueChanged.connect(
            lambda v: self.router.apply_nts1_slider("oscshp", v)
        )
        self.osc_alt_slider.valueChanged.connect(
            lambda v: self.router.apply_nts1_slider("oscalt", v)
        )

        # FILTER
        self.filt_cutoff_slider.valueChanged.connect(
            lambda v: self.router.apply_nts1_slider("cutoff", v)
        )
        self.filt_reso_slider.valueChanged.connect(
            lambda v: self.router.apply_nts1_slider("reso", v)
        )

        # LFO
        self.lfo_rate_slider.valueChanged.connect(lambda v: self.send_cc(24, v))
        self.lfo_int_slider.valueChanged.connect(
            lambda v: self.router.apply_nts1_slider("lfoint", v)
        )

        # EG
        self.eg_atk_slider.valueChanged.connect(lambda v: self.send_cc(16, v))
        self.eg_rel_slider.valueChanged.connect(lambda v: self.send_cc(19, v))

        # FX
        self.fx_delay_slider.valueChanged.connect(lambda v: self.send_cc(33, v))
        self.fx_reverb_slider.valueChanged.connect(
            lambda v: self.router.apply_nts1_slider("revmix", v)
        )

        # P-lock controls
        self.random_btn.clicked.connect(self.randomize_plocks)
        self.interp_combo.currentTextChanged.connect(self.on_interpolation_changed)

    def send_cc(self, cc: int, value: int):
        """Send raw CC via router."""
        self.router.send_cc(cc, value)

    def randomize_plocks(self):
        """Randomize all p-locks on current step."""
        for param in self.router.plock_seq.tracks.keys():
            self.router.randomize_plock_track(param, density=0.7, min_val=30, max_val=120)
        self.plock_status.setText(f"Step {self.current_step}: Randomized!")

    def on_interpolation_changed(self, mode_name: str):
        """Handle interpolation mode change."""
        mode_map = {
            "off": InterpolationMode.OFF,
            "linear": InterpolationMode.LINEAR,
            "cosine": InterpolationMode.COSINE,
        }
        mode = mode_map.get(mode_name, InterpolationMode.OFF)
        self.router.plock_seq.set_interpolation(mode)
        print(f"P-lock interpolation: {mode.value}")
