"""BANG! Sequencer Panel — 8 pattern slots + weighted advance + A/B compare.

Mirror of the webapp's sequencer/AB UI (web.py `/seq/*` and `/ab/*` routes).
Pure UI: emits signals only, no BangSession import. The main window wires the
signals to session.seq_save/seq_load/seq_clear/seq_advance/seq_set_weight/
seq_set_cycles and session.ab_store/ab_load, then refreshes the voice rack.

Slot clicks are dispatched through the active mode (Save / Load / Clear) so the
caller gets a semantic signal (save_requested/load_requested/clear_requested)
instead of a raw slot index it would have to interpret itself.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QSpinBox, QGroupBox, QButtonGroup,
)
from PySide6.QtCore import Qt, Signal

# App palette (matches generator_panel.py / voice_rack_widget.py conventions)
_SLATE      = "#141a26"
_BRASS      = "#b8956a"
_INK        = "#ddd6cc"
_BORDER     = "#202836"
_FILLED_BG  = "#3a4150"


class SequencerPanel(QWidget):
    """8 slot buttons + Save/Load/Clear modes + weights + Advance + A/B compare."""

    # Slot dispatch (0-indexed) — routed through the active mode.
    save_requested  = Signal(int)
    load_requested  = Signal(int)
    clear_requested = Signal(int)
    # Raw slot click (0-indexed) — emitted alongside the mode-specific signal.
    slot_clicked    = Signal(int)
    # Per-slot weight change (idx, weight 1-9).
    weight_changed  = Signal(int, int)

    cycles_changed    = Signal(int)
    advance_requested = Signal()

    store_a_requested = Signal()
    store_b_requested = Signal()
    load_a_requested  = Signal()
    load_b_requested  = Signal()

    _MODES = ("save", "load", "clear")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "load"
        self._slot_btns: list[QPushButton] = []
        self._weight_spins: list[QSpinBox] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.setStyleSheet(f"""
            QGroupBox {{ color: {_BRASS}; font-weight: bold; border: 1px solid {_BORDER};
                        margin-top: 8px; padding-top: 8px; }}
            QLabel {{ color: {_INK}; }}
            QSpinBox {{ background: {_SLATE}; color: {_INK}; border: 1px solid {_BORDER}; padding: 2px; }}
            QPushButton {{ background: {_BORDER}; color: {_INK}; border: 1px solid #3a4150; padding: 6px; }}
            QPushButton:hover {{ background: #2a3444; }}
            QPushButton:checked {{ background: {_BRASS}; color: #0a0e14; font-weight: bold; }}
        """)
        outer = QVBoxLayout(self)

        # --- Mode selector (Save / Load / Clear) ---
        mode_group = QGroupBox("Sequencer")
        mg = QVBoxLayout()
        mode_group.setLayout(mg)

        mode_row = QHBoxLayout()
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        for label, mode in (("📥 Save", "save"), ("📤 Load", "load"), ("🗑 Clear", "clear")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, m=mode: self._set_mode(m))
            self._mode_group.addButton(b)
            mode_row.addWidget(b)
            if mode == self._mode:
                b.setChecked(True)
        mg.addLayout(mode_row)

        # --- 8 slots (button + weight spin per column) ---
        slots_grid = QGridLayout()
        slots_grid.setHorizontalSpacing(4)
        for i in range(8):
            btn = QPushButton(str(i + 1))
            btn.setMinimumHeight(44)
            btn.clicked.connect(lambda _c=False, idx=i: self._on_slot(idx))
            slots_grid.addWidget(btn, 0, i)
            self._slot_btns.append(btn)

            spin = QSpinBox()
            spin.setRange(1, 9)
            spin.setValue(1)
            spin.setToolTip(f"Poids de sélection (advance) du slot {i + 1}")
            spin.valueChanged.connect(lambda w, idx=i: self.weight_changed.emit(idx, w))
            slots_grid.addWidget(spin, 1, i)
            self._weight_spins.append(spin)
        mg.addLayout(slots_grid)

        # --- Cycles + Advance ---
        adv_row = QHBoxLayout()
        adv_row.addWidget(QLabel("Cycles:"))
        self.cycles_spin = QSpinBox()
        self.cycles_spin.setRange(1, 8)
        self.cycles_spin.setValue(2)
        self.cycles_spin.valueChanged.connect(self.cycles_changed.emit)
        adv_row.addWidget(self.cycles_spin)
        adv_row.addStretch()
        self.advance_btn = QPushButton("▶ Advance")
        self.advance_btn.setStyleSheet(f"background: {_BRASS}; color: #0a0e14; font-weight: bold;")
        self.advance_btn.clicked.connect(self.advance_requested.emit)
        adv_row.addWidget(self.advance_btn)
        mg.addLayout(adv_row)

        outer.addWidget(mode_group)

        # --- A/B compare ---
        ab_group = QGroupBox("A/B Compare")
        ab = QGridLayout()
        ab_group.setLayout(ab)

        self._store_a_btn = QPushButton("Store A")
        self._store_b_btn = QPushButton("Store B")
        self._load_a_btn  = QPushButton("Load A")
        self._load_b_btn  = QPushButton("Load B")
        self._store_a_btn.clicked.connect(self.store_a_requested.emit)
        self._store_b_btn.clicked.connect(self.store_b_requested.emit)
        self._load_a_btn.clicked.connect(self.load_a_requested.emit)
        self._load_b_btn.clicked.connect(self.load_b_requested.emit)

        self.a_indicator = QLabel("A: vide")
        self.b_indicator = QLabel("B: vide")

        ab.addWidget(self._store_a_btn, 0, 0)
        ab.addWidget(self._load_a_btn,  0, 1)
        ab.addWidget(self.a_indicator,  0, 2)
        ab.addWidget(self._store_b_btn, 1, 0)
        ab.addWidget(self._load_b_btn,  1, 1)
        ab.addWidget(self.b_indicator,  1, 2)

        outer.addWidget(ab_group)
        outer.addStretch()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _set_mode(self, mode: str):
        if mode in self._MODES:
            self._mode = mode

    def _on_slot(self, idx: int):
        self.slot_clicked.emit(idx)
        if self._mode == "save":
            self.save_requested.emit(idx)
        elif self._mode == "clear":
            self.clear_requested.emit(idx)
        else:
            self.load_requested.emit(idx)

    # ------------------------------------------------------------------
    # State refresh (called by the main window after a session change)
    # ------------------------------------------------------------------

    def set_slot_states(self, filled: list[bool], current: int = -1):
        """Recolor slot buttons: filled slots get the brass-tinted fill, the
        current slot gets a brass border. `filled` is a list[bool] of length 8."""
        for i, btn in enumerate(self._slot_btns):
            is_filled = i < len(filled) and filled[i]
            bg = _FILLED_BG if is_filled else _SLATE
            border = f"2px solid {_BRASS}" if i == current else f"1px solid {_BORDER}"
            fg = _BRASS if is_filled else "#6a7180"
            btn.setStyleSheet(
                f"QPushButton {{ background: {bg}; color: {fg}; border: {border};"
                f" font-weight: bold; }} QPushButton:hover {{ background: #2a3444; }}"
            )

    def set_weights(self, weights: list[int]):
        """Sync the weight spinboxes from session state (no signal emission)."""
        for i, spin in enumerate(self._weight_spins):
            if i < len(weights):
                spin.blockSignals(True)
                spin.setValue(max(1, min(9, int(weights[i]))))
                spin.blockSignals(False)

    def set_cycles(self, n: int):
        self.cycles_spin.blockSignals(True)
        self.cycles_spin.setValue(max(1, min(8, int(n))))
        self.cycles_spin.blockSignals(False)

    def set_ab_states(self, a_filled: bool, b_filled: bool):
        self.a_indicator.setText("A: ●" if a_filled else "A: vide")
        self.b_indicator.setText("B: ●" if b_filled else "B: vide")
        self.a_indicator.setStyleSheet(f"color: {_BRASS};" if a_filled else "color: #6a7180;")
        self.b_indicator.setStyleSheet(f"color: {_BRASS};" if b_filled else "color: #6a7180;")


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    panel = SequencerPanel()
    panel.save_requested.connect(lambda i: print("save:", i))
    panel.load_requested.connect(lambda i: print("load:", i))
    panel.clear_requested.connect(lambda i: print("clear:", i))
    panel.slot_clicked.connect(lambda i: print("slot_clicked:", i))
    panel.weight_changed.connect(lambda i, w: print("weight:", i, w))
    panel.cycles_changed.connect(lambda n: print("cycles:", n))
    panel.advance_requested.connect(lambda: print("advance"))
    panel.store_a_requested.connect(lambda: print("store A"))
    panel.store_b_requested.connect(lambda: print("store B"))
    panel.load_a_requested.connect(lambda: print("load A"))
    panel.load_b_requested.connect(lambda: print("load B"))
    panel.set_slot_states([True, False, True, False, False, False, False, False], current=0)
    panel.set_ab_states(True, False)
    panel.show()
    print("✓ SequencerPanel constructed OK")
    if "--interactive" in sys.argv:
        sys.exit(app.exec())
