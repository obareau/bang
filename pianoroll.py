"""BANG! Pianoroll widget — per-voice step grid preview (real data).

Mirror of web.py's `_build_pianoroll_rows` (web.py:771-856): one row per
voice, cells colored by trigger/velocity/probability, drawn from the actual
BangSession.voices tuples instead of a fictional "current_pattern" key that
never existed on the real engine.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush

from bang_engine import compile_dna
import pattern_lib as pl

try:
    import babka as _babka
except ImportError:
    _babka = None


class PianorollWidget(QWidget):
    """Per-voice pattern preview, driven by a BangSession."""

    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.canvas = PianorollCanvas(session)
        scroll.setWidget(self.canvas)
        layout.addWidget(scroll)

        self.footer = QLabel("Ready — no pattern generated yet")
        self.footer.setStyleSheet("color: #7a8494; font-size: 11px; padding: 4px;")
        layout.addWidget(self.footer)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(200)

    def update_display(self):
        if self.session and self.session.voices:
            n = len(self.session.voices)
            bpm = self.session.last_p["bpm"] if self.session.last_p else "—"
            steps = self.session.last_p["steps"] if self.session.last_p else "—"
            self.footer.setText(f"Voices: {n} | Steps: {steps} | BPM: {bpm}")
        else:
            self.footer.setText("Ready — no pattern generated yet")
        self.canvas.update()
        self.canvas.updateGeometry()

    def set_playhead(self, step: int) -> None:
        self.canvas.playhead = step
        self.canvas.update()


class PianorollCanvas(QWidget):
    """Draws one horizontal row per voice, cells = DNA steps."""

    STEP_W = 16
    ROW_H = 22
    LEFT_MARGIN = 100
    MAX_STEPS = 64  # cap grid width for long patterns; still scrollable via steps count

    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.playhead = -1
        self.setStyleSheet("background: #0a0e14;")

    def _rows(self):
        """Build (name, color, cells[list[dict]]) per voice — mirror _build_pianoroll_rows."""
        if not self.session or not self.session.voices or not self.session.last_p:
            return []

        steps = self.session.last_p["steps"]
        rows = []
        bl_count = 0

        for note, dna, vtype in self.session.voices:
            if vtype == "cc":
                continue

            if vtype == "babka" and _babka is not None:
                try:
                    bsteps = _babka.parse(dna, cycle=0)
                except Exception:
                    bsteps = []
                tot_dur = sum(s.duration for s in bsteps) or 1.0
                cells = [{"trig": False, "opacity": 0.0} for _ in range(steps)]
                pos = 0.0
                for s in bsteps:
                    if s.trigger:
                        cyc_pos = pos
                        while cyc_pos < steps:
                            cell = int(cyc_pos)
                            if cell < steps:
                                opacity = round(0.35 + s.prob * 0.65, 2)
                                if not cells[cell]["trig"] or cells[cell]["opacity"] < opacity:
                                    cells[cell] = {"trig": True, "opacity": opacity}
                            cyc_pos += tot_dur
                    pos += s.duration
                name = pl.NOTE_NAMES.get(note, f"n{note}") + " ⚗"
                rows.append((name, "#e879f9", cells))
                continue

            compiled = compile_dna(dna) if dna else None
            dna_len = len(compiled) if compiled is not None else 1
            cells = []
            for i in range(steps):
                if compiled is None or dna_len == 0:
                    cells.append({"trig": False, "opacity": 0.0})
                    continue
                trig, vel, prob, ratch, jit = compiled[i % dna_len]
                cells.append({
                    "trig": bool(trig > 0),
                    "opacity": round(0.35 + prob * 0.65, 2) if trig > 0 else 0.0,
                    "vel": int(vel),
                })

            if vtype.startswith("vd"):
                idx = int(vtype[2:])
                color = pl.VD_PART_COLORS[idx % len(pl.VD_PART_COLORS)]
                name = pl.VD_PART_NAMES[idx % len(pl.VD_PART_NAMES)]
            elif vtype.startswith("vfm"):
                idx = int(vtype[3:])
                color = pl.VFM_PART_COLORS[idx % len(pl.VFM_PART_COLORS)]
                name = pl.VFM_PART_NAMES[idx % len(pl.VFM_PART_NAMES)]
            elif vtype.startswith("mf"):
                idx = int(vtype[2:])
                color = pl.MF_PART_COLORS[idx % len(pl.MF_PART_COLORS)]
                name = pl.MF_PART_NAMES[idx % len(pl.MF_PART_NAMES)]
            elif vtype.startswith("ksp"):
                idx = min(int(vtype[3:]) - 1, 3)
                color = pl.KSP_TRACK_COLORS[idx]
                name = f"KSP {pl.KSP_TRACK_NAMES[idx]}"
            elif vtype == "bl":
                color = "#a78bfa"
                name = "Bass ♩" if bl_count == 0 else f"Bass {bl_count + 1} ♩"
                bl_count += 1
            elif vtype == "vk":
                color = "#f97316"
                name = "VKick"
            else:
                color = pl.NOTE_COLOR.get(note, "#94a3b8")
                name = pl.NOTE_NAMES.get(note, f"n{note}")

            rows.append((name, color, cells))

        return rows

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0a0e14"))

        rows = self._rows()
        if not rows:
            painter.setPen(QColor("#7a8494"))
            painter.setFont(QFont("Menlo", 10))
            painter.drawText(self.rect(), Qt.AlignCenter, "No pattern yet — click Generate")
            return

        painter.setFont(QFont("Menlo", 9))

        for row_i, (name, color, cells) in enumerate(rows):
            y = row_i * self.ROW_H

            # Label background + text
            painter.fillRect(0, y, self.LEFT_MARGIN, self.ROW_H, QColor("#141a26"))
            painter.setPen(QColor(color))
            painter.drawText(6, y, self.LEFT_MARGIN - 10, self.ROW_H, Qt.AlignVCenter, name)

            base = QColor(color)
            for step_i, cell in enumerate(cells):
                x = self.LEFT_MARGIN + step_i * self.STEP_W
                cell_rect = (x, y + 2, self.STEP_W - 2, self.ROW_H - 4)

                # Grid cell background (every 4th slightly lighter, groove reference)
                bg = QColor("#161d2b") if (step_i // 4) % 2 == 0 else QColor("#12182400")
                painter.fillRect(x, y, self.STEP_W, self.ROW_H, QColor("#101623"))

                if cell.get("trig"):
                    c = QColor(base)
                    c.setAlphaF(min(1.0, max(0.25, cell.get("opacity", 0.6))))
                    painter.fillRect(*cell_rect, QBrush(c))

                if step_i == self.playhead:
                    painter.setPen(QPen(QColor("#e8c88a"), 2))
                    painter.drawRect(x, y, self.STEP_W - 1, self.ROW_H - 1)

            painter.setPen(QPen(QColor("#202836"), 1))
            painter.drawLine(0, y + self.ROW_H, self.LEFT_MARGIN + len(cells) * self.STEP_W, y + self.ROW_H)

        painter.setPen(QPen(QColor("#202836"), 1))
        painter.drawLine(self.LEFT_MARGIN, 0, self.LEFT_MARGIN, len(rows) * self.ROW_H)

    def sizeHint(self) -> QSize:
        rows = self._rows()
        n_rows = max(1, len(rows))
        n_steps = max((len(c) for _, _, c in rows), default=16)
        width = self.LEFT_MARGIN + n_steps * self.STEP_W
        height = n_rows * self.ROW_H
        return QSize(width, height)
