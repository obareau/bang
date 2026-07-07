"""BANG! DNA Grid Widget — interactive step-sequencer pattern editor.

Each voice carries a "DNA" string made of 5 symbols (bang_engine.DNA_SYMBOLS):

    x  hit strong / certain     (brass)
    -  silence                  (dim gray)
    ?  probabilistic hit (50%)  (amber)
    ↺  ratchet x3               (teal)
    ░  hit with timing jitter   (dusty pink)

The grid renders the DNA as a horizontal row of clickable cells. Clicking a
cell cycles its symbol in DNA_SYMBOLS order (x → - → ? → ↺ → ░ → x …) and
emits `dna_changed(str)` with the full updated DNA string.

Custom-painted single QWidget (not one sub-widget per cell): this gives tight
control over the classic 16-step sequencer look — cells grouped in blocks of 4
with a wider gap — plus a cheap playhead highlight and compact per-cell sizing
so grids up to 64 steps stay usable. This widget does NOT scroll internally; it
just lays out cells left-to-right and reports its width via sizeHint(). The
parent (VoiceRackWidget) is responsible for the outer QScrollArea.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen

from bang_engine import DNA_SYMBOLS


class DNAGridWidget(QWidget):
    """Clickable DNA step grid. Emits `dna_changed(str)` on every edit."""

    dna_changed = Signal(str)

    # Geometry — compact so 64-step grids remain usable.
    CELL_W = 22
    CELL_H = 26
    GAP = 2          # gap between adjacent cells
    BLOCK = 4        # cells per visual block
    BLOCK_GAP = 8    # extra gap after each block of 4

    # Per-symbol colors — cohesive with the app's dark slate / brass palette.
    SYMBOL_COLORS = {
        "x": QColor("#b8956a"),   # brass — hit strong
        "-": QColor("#3a4150"),   # dim gray — silence
        "?": QColor("#e0a458"),   # amber — probabilistic
        "↺": QColor("#5ec7c2"),   # teal — ratchet
        "░": QColor("#c98a9e"),   # dusty pink — jitter
    }
    # Text color drawn on top of each cell.
    SYMBOL_TEXT = {
        "x": QColor("#0a0e14"),
        "-": QColor("#7a8494"),
        "?": QColor("#0a0e14"),
        "↺": QColor("#0a0e14"),
        "░": QColor("#0a0e14"),
    }

    BG = QColor("#141a26")
    PLAYHEAD = QColor("#e8c88a")

    def __init__(self, dna: str = "", parent=None):
        super().__init__(parent)
        self._dna = dna or ""
        self._playhead = -1
        self.setMinimumHeight(self.CELL_H + 4)
        self.setMouseTracking(False)
        self.setToolTip("Click a step to cycle: x → - → ? → ↺ → ░")

    # -- public API --------------------------------------------------------

    def dna(self) -> str:
        """Return the current DNA string."""
        return self._dna

    def set_dna(self, dna: str) -> None:
        """Replace the whole grid without emitting `dna_changed` (no feedback loop)."""
        self._dna = dna or ""
        self.updateGeometry()
        self.update()

    def set_playhead(self, step: int) -> None:
        """Highlight the currently-playing step (-1 to clear). Driven by live clock."""
        if step != self._playhead:
            self._playhead = step
            self.update()

    # -- geometry helpers --------------------------------------------------

    def _cell_x(self, i: int) -> int:
        """Left x of cell `i`, accounting for block gaps."""
        return i * (self.CELL_W + self.GAP) + (i // self.BLOCK) * self.BLOCK_GAP

    def _cell_rect(self, i: int) -> QRect:
        return QRect(self._cell_x(i), 2, self.CELL_W, self.CELL_H)

    def _index_at(self, x: int, y: int) -> int:
        """Return the cell index at pixel (x, y), or -1 if none."""
        for i in range(len(self._dna)):
            if self._cell_rect(i).contains(x, y):
                return i
        return -1

    def _total_width(self) -> int:
        n = len(self._dna)
        if n == 0:
            return self.CELL_W
        return self._cell_x(n - 1) + self.CELL_W + 2

    def sizeHint(self) -> QSize:
        return QSize(self._total_width(), self.CELL_H + 4)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # -- interaction -------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        idx = self._index_at(pos.x(), pos.y())
        if idx < 0:
            return
        cur = self._dna[idx] if self._dna[idx] in DNA_SYMBOLS else DNA_SYMBOLS[0]
        nxt = DNA_SYMBOLS[(DNA_SYMBOLS.index(cur) + 1) % len(DNA_SYMBOLS)]
        chars = list(self._dna)
        chars[idx] = nxt
        self._dna = "".join(chars)
        self.update(self._cell_rect(idx))
        self.dna_changed.emit(self._dna)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.BG)

        font = QFont("Menlo", 11)
        painter.setFont(font)

        for i, ch in enumerate(self._dna):
            sym = ch if ch in DNA_SYMBOLS else "-"
            rect = self._cell_rect(i)

            # Cell body
            painter.fillRect(rect, self.SYMBOL_COLORS.get(sym, self.SYMBOL_COLORS["-"]))

            # Border — playhead gets a bright highlight, others a subtle edge.
            if i == self._playhead:
                painter.setPen(QPen(self.PLAYHEAD, 2))
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
            else:
                painter.setPen(QPen(QColor("#202836"), 1))
                painter.drawRect(rect)

            # Symbol glyph
            painter.setPen(self.SYMBOL_TEXT.get(sym, QColor("#7a8494")))
            painter.drawText(rect, Qt.AlignCenter, sym)

        painter.end()


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget as _W

    app = QApplication(sys.argv)
    win = _W()
    win.setStyleSheet("background:#0a0e14;")
    lay = QVBoxLayout(win)
    for dna in ("x---x---x---x---", "x-?-░-↺-x-?-░-↺-", "x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x"):
        g = DNAGridWidget(dna)
        g.dna_changed.connect(lambda s: print("dna_changed:", s))
        lay.addWidget(g)
    win.show()
    sys.exit(app.exec())
