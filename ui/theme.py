"""Thème SolarSound - Sombre avec accent jaune-orangé"""

STYLESHEET = """
/* ── Palette générale ── */
QWidget {
    background-color: #202020;
    color: #e8d5a0;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #202020;
}

/* ── Barre de titre de fenêtre ── */
QLabel#title_label {
    font-size: 22px;
    font-weight: bold;
    color: #f5a623;
    letter-spacing: 3px;
}

QLabel#subtitle_label {
    font-size: 11px;
    color: #7a6840;
    letter-spacing: 5px;
}

/* ── Boutons principaux (transport) ── */
QPushButton {
    background-color: #1e1a12;
    color: #e8d5a0;
    border: 1px solid #3d3420;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #2a2416;
    border-color: #f5a623;
    color: #f5a623;
}

QPushButton:pressed {
    background-color: #f5a623;
    color: #0f0d0a;
}

QPushButton:checked {
    background-color: #c47d0a;
    border-color: #f5a623;
    color: #0f0d0a;
    font-weight: bold;
}

QPushButton:disabled {
    color: #3d3420;
    border-color: #1e1a12;
    background-color: #0f0d0a;
}

/* ── Boutons icônes (play/pause/next/prev) ── */
QPushButton#btn_play {
    background-color: #f5a623;
    color: #0f0d0a;
    border-radius: 24px;
    font-size: 20px;
    font-weight: bold;
    min-width: 48px;
    min-height: 48px;
    max-width: 48px;
    max-height: 48px;
}

QPushButton#btn_play:hover {
    background-color: #ffbe4d;
    color: #0f0d0a;
}

QPushButton#btn_play:pressed {
    background-color: #c47d0a;
}

QPushButton#btn_prev, QPushButton#btn_next {
    background-color: #1e1a12;
    color: #f5a623;
    border-radius: 18px;
    font-size: 16px;
    min-width: 36px;
    min-height: 36px;
    max-width: 36px;
    max-height: 36px;
    border: 1px solid #3d3420;
}

QPushButton#btn_prev:hover, QPushButton#btn_next:hover {
    background-color: #2a2416;
    border-color: #f5a623;
}

QPushButton#btn_stop {
    background-color: #1e1a12;
    color: #e8d5a0;
    border-radius: 18px;
    font-size: 14px;
    min-width: 36px;
    min-height: 36px;
    max-width: 36px;
    max-height: 36px;
    border: 1px solid #3d3420;
}

/* ── Sliders ── */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background-color: #2a2416;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #c47d0a, stop:1 #f5a623);
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background-color: #f5a623;
    border: 2px solid #0f0d0a;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background-color: #ffbe4d;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}

QSlider::groove:vertical {
    border: none;
    width: 4px;
    background-color: #2a2416;
    border-radius: 2px;
}

QSlider::sub-page:vertical {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f5a623, stop:1 #c47d0a);
    border-radius: 2px;
}

QSlider::handle:vertical {
    background-color: #f5a623;
    border: 2px solid #0f0d0a;
    width: 14px;
    height: 14px;
    margin: 0 -5px;
    border-radius: 7px;
}

/* ── Liste de lecture ── */
QListWidget {
    background-color: #0c0a07;
    border: 1px solid #2a2416;
    border-radius: 8px;
    color: #e8d5a0;
    outline: none;
}

QListWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #1e1a12;
}

QListWidget::item:selected {
    background-color: #2a2008;
    color: #f5a623;
    border-left: 3px solid #f5a623;
}

QListWidget::item:hover {
    background-color: #1e1a12;
}

QListWidget#playlist_active_item {
    color: #f5a623;
}

/* ── GroupBox ── */
QGroupBox {
    border: 1px solid #2a2416;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    color: #f5a623;
    font-weight: bold;
    font-size: 12px;
    letter-spacing: 1px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #f5a623;
    background-color: #0f0d0a;
}

/* ── Labels ── */
QLabel {
    color: #e8d5a0;
}

QLabel#track_title {
    font-size: 16px;
    font-weight: bold;
    color: #f5c842;
}

QLabel#track_artist {
    font-size: 13px;
    color: #a08060;
}

QLabel#time_label {
    font-size: 12px;
    color: #7a6840;
    font-family: 'Consolas', 'Courier New', monospace;
}

/* ── Tabs ── */
QTabWidget::pane {
    border: 1px solid #2a2416;
    border-radius: 0 8px 8px 8px;
    background-color: #0f0d0a;
}

QTabBar::tab {
    background-color: #0c0a07;
    color: #7a6840;
    border: 1px solid #2a2416;
    padding: 8px 16px;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #0f0d0a;
    color: #f5a623;
    border-bottom: 1px solid #0f0d0a;
}

QTabBar::tab:hover {
    background-color: #1e1a12;
    color: #e8d5a0;
}

/* ── Scrollbar ── */
QScrollBar:vertical {
    background-color: #0c0a07;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background-color: #3d3420;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #f5a623;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #0c0a07;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background-color: #3d3420;
    border-radius: 4px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #f5a623;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ── Spinbox / Doublespinbox ── */
QDoubleSpinBox, QSpinBox {
    background-color: #1e1a12;
    border: 1px solid #3d3420;
    border-radius: 4px;
    color: #e8d5a0;
    padding: 3px 6px;
}

QDoubleSpinBox:focus, QSpinBox:focus {
    border-color: #f5a623;
}

/* ── ComboBox ── */
QComboBox {
    background-color: #1e1a12;
    border: 1px solid #3d3420;
    border-radius: 4px;
    color: #e8d5a0;
    padding: 4px 8px;
}

QComboBox:hover {
    border-color: #f5a623;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #1e1a12;
    border: 1px solid #3d3420;
    color: #e8d5a0;
    selection-background-color: #2a2008;
    selection-color: #f5a623;
}

/* ── Checkbox ── */
QCheckBox {
    color: #e8d5a0;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3d3420;
    border-radius: 3px;
    background-color: #1e1a12;
}

QCheckBox::indicator:checked {
    background-color: #f5a623;
    border-color: #f5a623;
    image: none;
}

QCheckBox::indicator:hover {
    border-color: #f5a623;
}

/* ── Séparateurs ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #2a2416;
}

/* ── MenuBar ── */
QMenuBar {
    background-color: #0c0a07;
    color: #e8d5a0;
    border-bottom: 1px solid #2a2416;
}

QMenuBar::item {
    padding: 6px 12px;
}

QMenuBar::item:selected {
    background-color: #1e1a12;
    color: #f5a623;
}

QMenu {
    background-color: #1e1a12;
    border: 1px solid #3d3420;
    color: #e8d5a0;
}

QMenu::item:selected {
    background-color: #2a2008;
    color: #f5a623;
}

QMenu::separator {
    height: 1px;
    background-color: #3d3420;
    margin: 4px 8px;
}

/* ── Status bar ── */
QStatusBar {
    background-color: #0c0a07;
    color: #7a6840;
    border-top: 1px solid #2a2416;
    font-size: 11px;
}

/* ── ToolTip ── */
QToolTip {
    background-color: #1e1a12;
    color: #f5a623;
    border: 1px solid #f5a623;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}
"""
