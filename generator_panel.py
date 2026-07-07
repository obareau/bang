"""BANG! Generator Panel — mode/chaos/bpm/scale controls driving BangSession.generate().

Mirror of the webapp's main generation form (web.py `_read_form`, the top of
index.html). Pure UI: emits signals, no BangSession import — the main window
wires generate_requested/export_requested to session.generate()/export_midi().
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QSlider, QLineEdit, QPushButton, QCheckBox,
    QGroupBox
)
from PySide6.QtCore import Qt, Signal

import pattern_lib as pl
from bang_engine import SCALE_INTERVALS

MODE_LABELS = {
    "morph": "Morph", "random": "Random", "weather": "Weather",
    "markov": "Markov", "phase2": "Phase 2", "noise": "Noise",
    "ambient": "Ambient", "babka": "Babka", "bassline": "Bassline",
    "volca_kick": "Volca Kick", "microfreak": "MicroFreak",
    "volca_fm": "Volca FM", "volca_drum": "Volca Drum",
    "keystep_pro": "Keystep Pro",
}


class GeneratorPanel(QWidget):
    """Mode + chaos + bpm + scale controls. Emits generate_requested(dict)."""

    generate_requested = Signal(dict)
    export_requested = Signal(dict)
    vary_all_requested = Signal()
    undo_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _slider_row(self, layout, label, lo, hi, default, row, scale=100):
        """Add a labeled slider (int 0-100 mapped to float lo-hi) + value label."""
        layout.addWidget(QLabel(label), row, 0)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, scale)
        slider.setValue(int(default * scale))
        layout.addWidget(slider, row, 1)
        value_lbl = QLabel(f"{default:.2f}")
        value_lbl.setMinimumWidth(40)
        value_lbl.setStyleSheet("color: #b8956a;")
        layout.addWidget(value_lbl, row, 2)
        slider.valueChanged.connect(lambda v: value_lbl.setText(f"{v / scale:.2f}"))
        return slider

    def _build_ui(self):
        self.setStyleSheet("""
            QGroupBox { color: #b8956a; font-weight: bold; border: 1px solid #202836;
                        margin-top: 8px; padding-top: 8px; }
            QLabel { color: #ddd6cc; }
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                background: #141a26; color: #ddd6cc; border: 1px solid #202836; padding: 3px;
            }
            QPushButton {
                background: #202836; color: #ddd6cc; border: 1px solid #3a4150; padding: 6px;
            }
            QPushButton:hover { background: #2a3444; }
        """)
        outer = QVBoxLayout(self)

        # --- Mode + core params ---
        gen_group = QGroupBox("Generator")
        grid = QGridLayout()
        gen_group.setLayout(grid)

        grid.addWidget(QLabel("Mode:"), 0, 0)
        self.mode_combo = QComboBox()
        for m in pl.GENERATION_MODES:
            self.mode_combo.addItem(MODE_LABELS.get(m, m), m)
        grid.addWidget(self.mode_combo, 0, 1, 1, 2)

        self.chaos_slider = self._slider_row(grid, "Chaos:", 0.0, 1.0, 0.30, 1)
        self.gravity_slider = self._slider_row(grid, "Gravity:", 0.0, 1.0, 0.70, 2)
        self.cc_depth_slider = self._slider_row(grid, "CC Depth:", 0.0, 1.0, 0.50, 3)
        self.swing_slider = self._slider_row(grid, "Swing:", 0.0, 1.0, 0.0, 4)
        self.microtiming_slider = self._slider_row(grid, "Microtiming:", 0.0, 1.0, 1.0, 5)

        grid.addWidget(QLabel("BPM:"), 6, 0)
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(1, 999)
        self.bpm_spin.setValue(110)
        grid.addWidget(self.bpm_spin, 6, 1, 1, 2)

        grid.addWidget(QLabel("Steps:"), 7, 0)
        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(1, 256)
        self.steps_spin.setValue(16)
        grid.addWidget(self.steps_spin, 7, 1, 1, 2)

        grid.addWidget(QLabel("Root:"), 8, 0)
        self.root_combo = QComboBox()
        self.root_combo.addItems(list(pl.ROOTS.keys()))
        self.root_combo.setCurrentText("A")
        grid.addWidget(self.root_combo, 8, 1)

        self.scale_combo = QComboBox()
        self.scale_combo.addItems(list(SCALE_INTERVALS.keys()))
        self.scale_combo.setCurrentText("penta_min")
        grid.addWidget(self.scale_combo, 8, 2)

        grid.addWidget(QLabel("Seed:"), 9, 0)
        self.seed_edit = QLineEdit()
        self.seed_edit.setPlaceholderText("(optionnel — reproductible)")
        grid.addWidget(self.seed_edit, 9, 1, 1, 2)

        self.temporal_check = QCheckBox("Temporal jitter (entropie microseconde)")
        grid.addWidget(self.temporal_check, 10, 0, 1, 3)

        grid.addWidget(QLabel("Filename:"), 11, 0)
        self.out_edit = QLineEdit("bang_out.mid")
        grid.addWidget(self.out_edit, 11, 1, 1, 2)

        grid.addWidget(QLabel("MIDI type:"), 12, 0)
        self.midi_type_combo = QComboBox()
        self.midi_type_combo.addItem("Type 1 (multi-piste)", 1)
        self.midi_type_combo.addItem("Type 0 (piste unique)", 0)
        grid.addWidget(self.midi_type_combo, 12, 1, 1, 2)

        outer.addWidget(gen_group)

        # --- Velocity shaping ---
        vel_group = QGroupBox("Velocity")
        vgrid = QGridLayout()
        vel_group.setLayout(vgrid)

        vgrid.addWidget(QLabel("Floor:"), 0, 0)
        self.vel_floor_spin = QSpinBox()
        self.vel_floor_spin.setRange(0, 126)
        self.vel_floor_spin.setValue(0)
        vgrid.addWidget(self.vel_floor_spin, 0, 1)

        vgrid.addWidget(QLabel("Ceiling:"), 0, 2)
        self.vel_ceiling_spin = QSpinBox()
        self.vel_ceiling_spin.setRange(1, 127)
        self.vel_ceiling_spin.setValue(127)
        vgrid.addWidget(self.vel_ceiling_spin, 0, 3)

        self.vel_curve_slider = self._slider_row(vgrid, "Curve:", 0.1, 4.0, 1.0, 1)

        vgrid.addWidget(QLabel("Humanize:"), 2, 0)
        self.vel_humanize_spin = QSpinBox()
        self.vel_humanize_spin.setRange(0, 40)
        self.vel_humanize_spin.setValue(0)
        vgrid.addWidget(self.vel_humanize_spin, 2, 1)

        outer.addWidget(vel_group)

        # --- Transport / actions ---
        actions = QHBoxLayout()
        self.generate_btn = QPushButton("⚡ Generate")
        self.generate_btn.setStyleSheet("background: #b8956a; color: #0a0e14; font-weight: bold;")
        self.export_btn = QPushButton("💾 Export MIDI")
        self.vary_btn = QPushButton("🎲 Vary All")
        self.undo_btn = QPushButton("↩ Undo")
        actions.addWidget(self.generate_btn)
        actions.addWidget(self.export_btn)
        actions.addWidget(self.vary_btn)
        actions.addWidget(self.undo_btn)
        outer.addLayout(actions)

        outer.addStretch()

        self.generate_btn.clicked.connect(self._emit_generate)
        self.export_btn.clicked.connect(self._emit_export)
        self.vary_btn.clicked.connect(self.vary_all_requested.emit)
        self.undo_btn.clicked.connect(self.undo_requested.emit)

    def params(self) -> dict:
        """Collect current form values (mirror pattern_lib.read_form kwargs)."""
        return {
            "mode": self.mode_combo.currentData(),
            "chaos": self.chaos_slider.value() / 100,
            "bpm": self.bpm_spin.value(),
            "steps": self.steps_spin.value(),
            "gravity": self.gravity_slider.value() / 100,
            "cc_depth": self.cc_depth_slider.value() / 100,
            "root": self.root_combo.currentText(),
            "scale": self.scale_combo.currentText(),
            "seed": self.seed_edit.text().strip(),
            "swing": self.swing_slider.value() / 100,
            "vel_floor": self.vel_floor_spin.value(),
            "vel_ceiling": self.vel_ceiling_spin.value(),
            "vel_curve": self.vel_curve_slider.value() / 100,
            "vel_humanize": self.vel_humanize_spin.value(),
            "microtiming": self.microtiming_slider.value() / 100,
            "temporal": self.temporal_check.isChecked(),
            "out": self.out_edit.text().strip() or "bang_out.mid",
            "midi_type": self.midi_type_combo.currentData(),
        }

    def _emit_generate(self):
        self.generate_requested.emit(self.params())

    def _emit_export(self):
        self.export_requested.emit(self.params())


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    panel = GeneratorPanel()
    panel.generate_requested.connect(lambda p: print("generate:", p))
    panel.export_requested.connect(lambda p: print("export:", p))
    panel.show()
    print("✓ GeneratorPanel constructed OK")
    if "--interactive" in sys.argv:
        sys.exit(app.exec())
