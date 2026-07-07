"""BANG! Pianoroll widget — real-time pattern visualization."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea
from PySide6.QtCore import Qt, QRect, QSize, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from typing import Optional


class PianorollWidget(QWidget):
    """Real-time piano roll visualization of MIDI patterns."""

    NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    START_OCTAVE = 2
    NUM_OCTAVES = 4
    NUM_KEYS = NUM_OCTAVES * 12

    def __init__(self, engine=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setMinimumHeight(400)
        self.setMinimumWidth(800)

        # Layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Header: time grid
        self.header = PianorollHeader()
        layout.addWidget(self.header)

        # Scroll area with pianoroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.canvas = PianorollCanvas(self.engine)
        scroll.setWidget(self.canvas)
        layout.addWidget(scroll)

        # Footer: info
        self.footer = QLabel("Ready — no pattern loaded")
        self.footer.setStyleSheet("color: #7a8494; font-size: 11px; padding: 4px;")
        layout.addWidget(self.footer)

        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(100)

    def update_display(self):
        """Update pianoroll from engine state."""
        if self.engine:
            pattern = self.engine.state.get("current_pattern", {})
            voices = self.engine.state.get("voices", [])
            info = f"Voices: {len(voices)} | Notes: {len(pattern)} | BPM: {self.engine.state.get('bpm', 120)}"
            self.footer.setText(info)
        self.canvas.update()


class PianorollHeader(QWidget):
    """Time grid header."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setStyleSheet("background: #141a26; border-bottom: 1px solid #202836;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#141a26"))

        # Draw beat markers
        step_width = 40
        for i in range(16):
            x = 80 + i * step_width
            painter.drawLine(x, 0, x, self.height())
            painter.drawText(x + 5, 15, f"{i+1}")

        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class PianorollCanvas(QWidget):
    """Main pianoroll canvas for note display."""

    STEP_WIDTH = 40
    KEY_HEIGHT = 16
    LEFT_MARGIN = 80

    def __init__(self, engine=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setMinimumSize(800, PianorollWidget.NUM_KEYS * self.KEY_HEIGHT)
        self.setStyleSheet("background: #0a0e14;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0a0e14"))

        # Draw piano keys (left side)
        self.draw_keys(painter)

        # Draw grid + notes
        self.draw_grid(painter)
        self.draw_notes(painter)

    def draw_keys(self, painter: QPainter):
        """Draw piano key labels."""
        painter.setFont(QFont("Menlo", 9))
        painter.setPen(QColor("#7a8494"))

        for i in range(PianorollWidget.NUM_KEYS):
            octave = PianorollWidget.START_OCTAVE + i // 12
            note_name = PianorollWidget.NOTES[i % 12]
            y = self.rect().height() - (i + 1) * self.KEY_HEIGHT

            # Background
            bg_color = QColor("#1a2135") if (i % 12) in [1, 3, 6, 8, 10] else QColor("#141a26")
            painter.fillRect(0, y, self.LEFT_MARGIN, self.KEY_HEIGHT, bg_color)

            # Label
            text = f"{note_name}{octave}"
            painter.drawText(5, y, self.LEFT_MARGIN - 10, self.KEY_HEIGHT, Qt.AlignRight | Qt.AlignVCenter, text)

        # Separator
        painter.setPen(QPen(QColor("#202836"), 1))
        painter.drawLine(self.LEFT_MARGIN, 0, self.LEFT_MARGIN, self.rect().height())

    def draw_grid(self, painter: QPainter):
        """Draw time grid."""
        painter.setPen(QPen(QColor("#202836"), 1))

        # Vertical lines (steps)
        for step in range(16):
            x = self.LEFT_MARGIN + step * self.STEP_WIDTH
            painter.drawLine(x, 0, x, self.rect().height())

        # Horizontal lines (notes)
        for i in range(PianorollWidget.NUM_KEYS + 1):
            y = self.rect().height() - i * self.KEY_HEIGHT
            painter.drawLine(self.LEFT_MARGIN, y, self.rect().width(), y)

    def draw_notes(self, painter: QPainter):
        """Draw note rectangles from engine pattern."""
        if not self.engine:
            return

        pattern = self.engine.state.get("current_pattern", {})
        if not pattern:
            return

        painter.setPen(QPen(QColor("#b8956a"), 1))

        for note_event in pattern.get("notes", []):
            step = note_event.get("step", 0)
            note = note_event.get("note", 60)
            duration = note_event.get("duration", 1)
            velocity = note_event.get("velocity", 100)

            # Map note to key index
            key_index = note - (PianorollWidget.START_OCTAVE * 12)
            if not (0 <= key_index < PianorollWidget.NUM_KEYS):
                continue

            # Calculate rect
            x = self.LEFT_MARGIN + step * self.STEP_WIDTH + 2
            y = self.rect().height() - (key_index + 1) * self.KEY_HEIGHT + 2
            w = duration * self.STEP_WIDTH - 4
            h = self.KEY_HEIGHT - 4

            # Draw note
            color = QColor("#b8956a")
            color.setAlpha(100 + int(velocity / 2.55))
            painter.fillRect(x, y, w, h, QBrush(color))
            painter.drawRect(x, y, w, h)

    def sizeHint(self) -> QSize:
        """Suggest size based on content."""
        width = self.LEFT_MARGIN + 16 * self.STEP_WIDTH
        height = PianorollWidget.NUM_KEYS * self.KEY_HEIGHT
        return QSize(width, height)
