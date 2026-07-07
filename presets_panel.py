"""BANG! Presets Panel — drum machines, grooves, KSP presets + session I/O.

Pure UI: emits signals carrying the chosen preset name (or file path). The main
window (qt_app.py) wires these to BangSession.apply_drum_preset / apply_groove /
apply_ksp_preset / export_session_json / import_session_json.

Palette matches the rest of the app (dark slate #141a26 bg, brass #b8956a
accent) — see generator_panel.py / voice_rack_widget.py for the shared QSS.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QGroupBox, QFileDialog,
)
from PySide6.QtCore import Signal

import presets_lib as pr

_PANEL_QSS = """
    QGroupBox { color: #b8956a; font-weight: bold; border: 1px solid #202836;
                margin-top: 8px; padding-top: 8px; }
    QComboBox {
        background: #141a26; color: #ddd6cc; border: 1px solid #202836; padding: 3px;
    }
    QPushButton {
        background: #202836; color: #ddd6cc; border: 1px solid #3a4150; padding: 6px;
    }
    QPushButton:hover { background: #2a3444; }
"""


class PresetsPanel(QWidget):
    """Drum machine / groove / KSP preset pickers + session export/import.

    Signals:
        drum_preset_requested(str)     — apply DRUM_PRESETS[name]
        groove_requested(str)          — apply GROOVE_PRESETS[name]
        ksp_preset_requested(str)      — apply KSP_PRESETS_BUILTIN[name]
        session_exported(str)          — user chose a save path (write here)
        session_import_requested(str)  — user chose a file path (load this)
    """

    drum_preset_requested = Signal(str)
    groove_requested = Signal(str)
    ksp_preset_requested = Signal(str)
    session_exported = Signal(str)
    session_import_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_PANEL_QSS)
        self._build_ui()

    def _picker_group(self, title: str, items, apply_slot) -> tuple[QGroupBox, QComboBox]:
        group = QGroupBox(title)
        row = QHBoxLayout(group)
        combo = QComboBox()
        combo.addItems(list(items))
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(apply_slot)
        row.addWidget(combo, 1)
        row.addWidget(apply_btn)
        return group, combo

    def _build_ui(self):
        outer = QVBoxLayout(self)

        drum_group, self.drum_combo = self._picker_group(
            "Drum Machine", pr.DRUM_PRESETS.keys(), self._emit_drum)
        outer.addWidget(drum_group)

        groove_group, self.groove_combo = self._picker_group(
            "Groove", pr.GROOVE_PRESETS.keys(), self._emit_groove)
        outer.addWidget(groove_group)

        ksp_group, self.ksp_combo = self._picker_group(
            "KSP Scale Preset", pr.KSP_PRESETS_BUILTIN.keys(), self._emit_ksp)
        outer.addWidget(ksp_group)

        session_group = QGroupBox("Session")
        srow = QHBoxLayout(session_group)
        self.export_btn = QPushButton("💾 Export Session (JSON)")
        self.import_btn = QPushButton("📂 Import Session (JSON)")
        self.export_btn.clicked.connect(self._pick_export)
        self.import_btn.clicked.connect(self._pick_import)
        srow.addWidget(self.export_btn)
        srow.addWidget(self.import_btn)
        outer.addWidget(session_group)

        outer.addStretch()

    def _emit_drum(self):
        name = self.drum_combo.currentText()
        if name:
            self.drum_preset_requested.emit(name)

    def _emit_groove(self):
        name = self.groove_combo.currentText()
        if name:
            self.groove_requested.emit(name)

    def _emit_ksp(self):
        name = self.ksp_combo.currentText()
        if name:
            self.ksp_preset_requested.emit(name)

    def _pick_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Session", "bang-session.json", "JSON files (*.json)")
        if path:
            self.session_exported.emit(path)

    def _pick_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Session", "", "JSON files (*.json)")
        if path:
            self.session_import_requested.emit(path)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    panel = PresetsPanel()
    panel.drum_preset_requested.connect(lambda n: print("drum:", n))
    panel.groove_requested.connect(lambda n: print("groove:", n))
    panel.ksp_preset_requested.connect(lambda n: print("ksp:", n))
    panel.session_exported.connect(lambda p: print("export:", p))
    panel.session_import_requested.connect(lambda p: print("import:", p))
    panel.show()

    # Smoke test: verify combos populated from presets_lib.
    assert panel.drum_combo.count() == len(pr.DRUM_PRESETS)
    assert panel.groove_combo.count() == len(pr.GROOVE_PRESETS)
    assert panel.ksp_combo.count() == len(pr.KSP_PRESETS_BUILTIN)
    print("✓ PresetsPanel constructed OK "
          f"({panel.drum_combo.count()} drums, {panel.groove_combo.count()} grooves, "
          f"{panel.ksp_combo.count()} KSP)")
    if "--interactive" in sys.argv:
        sys.exit(app.exec())
