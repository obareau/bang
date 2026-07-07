"""BANG! Song Panel — macro-arrangement export controls.

Mirror of the webapp's song export form (web.py `/export/song`). Pure UI: emits
export_song_requested(dict) with {chaos, bpm, gravity, cc_depth, out}. The main
window wires it to session.export_song_midi(...).

Reuses the same labeled-slider convention as generator_panel.py so the two
panels feel identical.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QSlider,
    QSpinBox, QLineEdit, QPushButton, QGroupBox,
)
from PySide6.QtCore import Qt, Signal

_SLATE  = "#141a26"
_BRASS  = "#b8956a"
_INK    = "#ddd6cc"
_BORDER = "#202836"

_STRUCTURE_LABEL = (
    "Intro ×4 → Transition → Couplet ×8 → Break → Couplet2 ×4 → "
    "Climax ×4 → Break2 ×2 → Outro ×2 → Fin ×4"
)


class SongPanel(QWidget):
    """chaos/bpm/gravity/cc_depth + filename + Export Song button."""

    export_song_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _slider_row(self, layout, label, default, row, scale=100):
        """Labeled slider (int 0-scale mapped to 0..1 float) + value label —
        same visual convention as generator_panel.GeneratorPanel._slider_row."""
        layout.addWidget(QLabel(label), row, 0)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, scale)
        slider.setValue(int(default * scale))
        layout.addWidget(slider, row, 1)
        value_lbl = QLabel(f"{default:.2f}")
        value_lbl.setMinimumWidth(40)
        value_lbl.setStyleSheet(f"color: {_BRASS};")
        layout.addWidget(value_lbl, row, 2)
        slider.valueChanged.connect(lambda v: value_lbl.setText(f"{v / scale:.2f}"))
        return slider

    def _build_ui(self):
        self.setStyleSheet(f"""
            QGroupBox {{ color: {_BRASS}; font-weight: bold; border: 1px solid {_BORDER};
                        margin-top: 8px; padding-top: 8px; }}
            QLabel {{ color: {_INK}; }}
            QSpinBox, QLineEdit {{
                background: {_SLATE}; color: {_INK}; border: 1px solid {_BORDER}; padding: 3px;
            }}
            QPushButton {{ background: {_BORDER}; color: {_INK}; border: 1px solid #3a4150; padding: 6px; }}
            QPushButton:hover {{ background: #2a3444; }}
        """)
        outer = QVBoxLayout(self)

        group = QGroupBox("Song Mode")
        grid = QGridLayout()
        group.setLayout(grid)

        self.chaos_slider    = self._slider_row(grid, "Chaos:",    0.50, 0)
        self.gravity_slider  = self._slider_row(grid, "Gravity:",  0.70, 1)
        self.cc_depth_slider = self._slider_row(grid, "CC Depth:", 0.50, 2)

        grid.addWidget(QLabel("BPM:"), 3, 0)
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(1, 999)
        self.bpm_spin.setValue(110)
        grid.addWidget(self.bpm_spin, 3, 1, 1, 2)

        grid.addWidget(QLabel("Filename:"), 4, 0)
        self.out_edit = QLineEdit("bang_song.mid")
        grid.addWidget(self.out_edit, 4, 1, 1, 2)

        outer.addWidget(group)

        # Structure description (read-only)
        struct = QLabel(_STRUCTURE_LABEL)
        struct.setWordWrap(True)
        struct.setStyleSheet(
            f"color: #9aa2b0; font-style: italic; padding: 4px; "
            f"border: 1px solid {_BORDER}; background: {_SLATE};"
        )
        outer.addWidget(struct)

        actions = QHBoxLayout()
        self.export_btn = QPushButton("🎵 Export Song")
        self.export_btn.setStyleSheet(f"background: {_BRASS}; color: #0a0e14; font-weight: bold;")
        self.export_btn.clicked.connect(self._emit_export)
        actions.addWidget(self.export_btn)
        outer.addLayout(actions)

        outer.addStretch()

    def params(self) -> dict:
        return {
            "chaos":    self.chaos_slider.value() / 100,
            "gravity":  self.gravity_slider.value() / 100,
            "cc_depth": self.cc_depth_slider.value() / 100,
            "bpm":      self.bpm_spin.value(),
            "out":      self.out_edit.text().strip() or "bang_song.mid",
        }

    def _emit_export(self):
        self.export_song_requested.emit(self.params())


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    panel = SongPanel()
    panel.export_song_requested.connect(lambda p: print("export_song:", p))
    panel.show()
    print("✓ SongPanel constructed OK")
    if "--interactive" in sys.argv:
        sys.exit(app.exec())
