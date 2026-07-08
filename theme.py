"""BANG! Qt6 — app-wide theme (dark CRT/terminal aesthetic, matching the webapp).

The webapp (templates/index.html) uses a distinctive monochrome amber-on-near-
black terminal look: JetBrains Mono everywhere, a single accent hue for all
chrome (borders/highlights/labels), uppercase letter-spaced section titles,
and a very dark background (#030303/#090909) — not the generic multi-color
"dark slate SaaS dashboard" look each Qt widget ended up with when built
piecemeal. This module is the one place that sets the chrome palette/type so
every widget looks consistent; per-voice badge/DNA-cell colors (functional
coding, not chrome) are untouched — those still come from pattern_lib's color
tables and stay multi-hue on purpose.

Usage: `app.setStyleSheet(THEME_QSS)` once, right after creating the
QApplication, before any windows are shown. Local widget-level
`setStyleSheet()` calls still override these rules for that widget/its
children (normal Qt cascade — more specific selectors win), so existing
per-widget styles keep working; this just fixes everything nobody styled
explicitly (QTabWidget tabs, QScrollBar, base QPushButton/QComboBox/QSpinBox
look) and gives buttons/borders one consistent accent instead of scattered
ad hoc colors.
"""

# Single accent hue — matches the brass tone already used as the primary
# accent across generator_panel.py / voice_rack_widget.py / dna_grid_widget.py,
# so this theme reinforces the existing choice instead of introducing a
# competing color.
ACCENT = "#e8a33d"
ACCENT_DIM = "#8a6a35"
BG = "#0a0a0a"
SURFACE = "#111111"
SURFACE_2 = "#161616"
BORDER = "#2a2218"
TEXT = "#d8cdb8"
TEXT_MUTED = "#7a6f5c"

FONT_FAMILY = '"JetBrains Mono", "Fira Code", "Cascadia Code", Consolas, monospace'
# Buttons/labels carry emoji glyphs (🎲 ⟲ ⇄ ⚡ 💾 ▶ ⏹ 🔊 ...) that monospace
# coding fonts don't include — forcing FONT_FAMILY on them renders mismatched
# tofu/fallback glyphs. Only apply monospace to widgets showing tabular/code
# data (numeric fields, DNA text, logs); everything else keeps the system UI
# font, which has real emoji coverage.

THEME_QSS = f"""
QMainWindow, QWidget {{
    background: {BG};
    color: {TEXT};
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QListWidget {{
    font-family: {FONT_FAMILY};
}}

QGroupBox {{
    color: {ACCENT};
    font-weight: bold;
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
    border: 1px solid {BORDER};
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
    background: {SURFACE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}

QLabel {{
    color: {TEXT};
    background: transparent;
}}

QPushButton {{
    background: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 5px 10px;
}}
QPushButton:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
}}
QPushButton:pressed {{
    background: {ACCENT_DIM};
    color: {BG};
}}
QPushButton:checked {{
    background: {ACCENT};
    color: {BG};
    border-color: {ACCENT};
}}
QPushButton:disabled {{
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QListWidget {{
    background: {BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 3px 5px;
    selection-background-color: {ACCENT};
    selection-color: {BG};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border-left: 1px solid {BORDER};
    width: 16px;
}}
QComboBox::down-arrow {{
    width: 6px; height: 6px;
    image: none;
    background: {ACCENT};
    margin-right: 5px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {ACCENT};
    selection-background-color: {ACCENT};
    selection-color: {BG};
}}

QSlider::groove:horizontal {{
    background: {SURFACE_2};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 12px;
    margin: -5px 0;
    border-radius: 2px;
}}
QSlider::handle:horizontal:hover {{
    background: {TEXT};
}}

QCheckBox {{
    color: {TEXT};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 13px; height: 13px;
    border: 1px solid {BORDER};
    background: {BG};
    border-radius: 2px;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BG};
    top: -1px;
}}
QTabBar::tab {{
    background: {SURFACE};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 6px 12px;
    margin-right: 2px;
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
}}
QTabBar::tab:selected {{
    background: {BG};
    color: {ACCENT};
    border-color: {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
}}

QScrollBar:vertical {{
    background: {BG};
    width: 11px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT_DIM}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: {BG};
    height: 11px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT_DIM}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QSplitter::handle {{
    background: {BORDER};
}}
QSplitter::handle:hover {{
    background: {ACCENT_DIM};
}}

QStatusBar {{
    background: {SURFACE};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}

QScrollArea {{
    border: none;
    background: {BG};
}}

QToolTip {{
    background: {SURFACE};
    color: {ACCENT};
    border: 1px solid {ACCENT};
    padding: 3px 6px;
}}

QDialog {{
    background: {BG};
}}

QMessageBox {{
    background: {SURFACE};
}}
"""
