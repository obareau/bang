"""BANG! OSC Debugger — real-time OSC message monitoring."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, QDateTime
from PySide6.QtGui import QColor, QFont
from collections import deque
from datetime import datetime


class OSCDebuggerWidget(QWidget):
    """Monitor and debug OSC messages (TX/RX)."""

    def __init__(self, engine=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.messages = deque(maxlen=100)  # Keep last 100 messages
        self.init_ui()

        # Simulation timer (until real OSC is connected)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(500)

    def init_ui(self):
        """Build OSC debugger UI."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("e.g. /pattern, /note")
        self.filter_input.textChanged.connect(self.update_display)
        filter_layout.addWidget(self.filter_input)

        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.setMaximumWidth(80)
        clear_btn.clicked.connect(self.clear_messages)
        filter_layout.addWidget(clear_btn)

        layout.addLayout(filter_layout)

        # Messages table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Time", "Direction", "Address", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setMaximumHeight(300)
        self.table.setFont(QFont("Menlo", 9))
        layout.addWidget(self.table)

        # Stats bar
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("Messages: 0 (TX: 0, RX: 0)")
        self.stats_label.setStyleSheet("color: #7a8494; font-size: 11px;")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

    def add_message(self, direction: str, address: str, value: str):
        """Add OSC message to log (direction: 'TX' or 'RX')."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.messages.append({
            "time": timestamp,
            "direction": direction,
            "address": address,
            "value": value
        })

    def update_display(self):
        """Update table with filtered messages."""
        filter_text = self.filter_input.text().lower()
        self.table.setRowCount(0)

        # Count stats
        tx_count = sum(1 for m in self.messages if m["direction"] == "TX")
        rx_count = sum(1 for m in self.messages if m["direction"] == "RX")
        self.stats_label.setText(f"Messages: {len(self.messages)} (TX: {tx_count}, RX: {rx_count})")

        # Add filtered rows
        row = 0
        for msg in reversed(list(self.messages)):
            if filter_text and filter_text not in msg["address"].lower():
                continue

            self.table.insertRow(row)

            # Time
            time_item = QTableWidgetItem(msg["time"])
            time_item.setForeground(QColor("#7a8494"))
            self.table.setItem(row, 0, time_item)

            # Direction
            direction_item = QTableWidgetItem(msg["direction"])
            direction_color = QColor("#5ec75c") if msg["direction"] == "TX" else QColor("#b8956a")
            direction_item.setForeground(direction_color)
            direction_item.setFont(QFont("Menlo", 9, QFont.Bold))
            self.table.setItem(row, 1, direction_item)

            # Address
            addr_item = QTableWidgetItem(msg["address"])
            addr_item.setForeground(QColor("#ddd6cc"))
            self.table.setItem(row, 2, addr_item)

            # Value
            val_item = QTableWidgetItem(msg["value"])
            val_item.setForeground(QColor("#b8956a"))
            self.table.setItem(row, 3, val_item)

            row += 1

    def clear_messages(self):
        """Clear all logged messages."""
        self.messages.clear()
        self.table.setRowCount(0)
        self.stats_label.setText("Messages: 0 (TX: 0, RX: 0)")

    def log_example_messages(self):
        """Add example messages for testing (remove when real OSC hooked up)."""
        examples = [
            ("TX", "/bang/play", "start"),
            ("RX", "/nts1/osc", "cutoff=2400 reso=50"),
            ("TX", "/pattern/step", "0=60:100"),
            ("RX", "/ping", "pong"),
        ]
        for direction, address, value in examples:
            self.add_message(direction, address, value)
        self.update_display()
