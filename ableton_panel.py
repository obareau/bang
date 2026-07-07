"""BANG! Ableton Panel — OSC bridge UI (tempo sync + push pattern as clips)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QSpinBox, QPushButton, QGroupBox,
)
from PySide6.QtCore import Signal


class AbletonPanel(QWidget):
    """AbletonOSC config + actions. No BangSession/OSC import — signals only."""

    sync_bpm_requested = Signal(str, int)                    # host, port
    send_requested = Signal(str, int, int, int)              # host, port, track_offset, slot
    config_changed = Signal(str, int, int, int)              # host, port, track_offset, slot

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QGroupBox { color: #b8956a; font-weight: bold; border: 1px solid #202836;
                        margin-top: 8px; padding-top: 8px; }
            QLabel { color: #ddd6cc; }
            QLineEdit, QSpinBox {
                background: #141a26; color: #ddd6cc; border: 1px solid #202836; padding: 3px;
            }
            QPushButton {
                background: #202836; color: #ddd6cc; border: 1px solid #3a4150; padding: 6px;
            }
            QPushButton:hover { background: #2a3444; }
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        group = QGroupBox("Ableton Live (AbletonOSC)")
        grid = QGridLayout()
        group.setLayout(grid)

        grid.addWidget(QLabel("Host:"), 0, 0)
        self.host_edit = QLineEdit("127.0.0.1")
        grid.addWidget(self.host_edit, 0, 1)

        grid.addWidget(QLabel("Port:"), 0, 2)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(11000)
        grid.addWidget(self.port_spin, 0, 3)

        grid.addWidget(QLabel("Track offset:"), 1, 0)
        self.track_offset_spin = QSpinBox()
        self.track_offset_spin.setRange(0, 127)
        grid.addWidget(self.track_offset_spin, 1, 1)

        grid.addWidget(QLabel("Slot:"), 1, 2)
        self.slot_spin = QSpinBox()
        self.slot_spin.setRange(0, 127)
        grid.addWidget(self.slot_spin, 1, 3)

        outer.addWidget(group)

        actions = QHBoxLayout()
        self.sync_btn = QPushButton("🔄 Sync BPM from Live")
        self.send_btn = QPushButton("📤 Send pattern to Live")
        self.send_btn.setStyleSheet(
            "QPushButton { background: #b8956a; color: #0a0e14; font-weight: bold; }"
        )
        actions.addWidget(self.sync_btn)
        actions.addWidget(self.send_btn)
        outer.addLayout(actions)

        self.status_label = QLabel(
            "Requires AbletonOSC (github.com/ideoforms/AbletonOSC) running inside Live."
        )
        self.status_label.setStyleSheet("color: #7a8494; font-size: 10px;")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        outer.addStretch()

        self.sync_btn.clicked.connect(self._emit_sync)
        self.send_btn.clicked.connect(self._emit_send)
        for w in (self.host_edit, self.port_spin, self.track_offset_spin, self.slot_spin):
            sig = w.textChanged if isinstance(w, QLineEdit) else w.valueChanged
            sig.connect(self._emit_config)

    def _config(self) -> tuple[str, int, int, int]:
        return (
            self.host_edit.text().strip() or "127.0.0.1",
            self.port_spin.value(),
            self.track_offset_spin.value(),
            self.slot_spin.value(),
        )

    def _emit_config(self, *_args) -> None:
        self.config_changed.emit(*self._config())

    def _emit_sync(self) -> None:
        host, port, _, _ = self._config()
        self.sync_bpm_requested.emit(host, port)

    def _emit_send(self) -> None:
        self.send_requested.emit(*self._config())

    def set_status(self, text: str, ok: bool = True) -> None:
        color = "#5ec7c2" if ok else "#c98a9e"
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.status_label.setText(text)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    panel = AbletonPanel()
    panel.sync_bpm_requested.connect(lambda h, p: print("sync:", h, p))
    panel.send_requested.connect(lambda h, p, t, s: print("send:", h, p, t, s))
    panel.show()
    print("✓ AbletonPanel constructed OK")
