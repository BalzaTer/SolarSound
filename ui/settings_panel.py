"""
Panneau de paramètres SolarSound
- Raccourcis clavier personnalisables
- Couleurs de l'interface (thème live)
- Police d'écriture personnalisée
"""

import json
import os
from typing import Dict, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QGroupBox,
    QLabel, QPushButton, QLineEdit, QFontComboBox, QSpinBox,
    QColorDialog, QFrame, QScrollArea, QGridLayout, QComboBox,
    QCheckBox, QDoubleSpinBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPalette


# ── Données de configuration ─────────────────────────────────────────────────

DEFAULT_SHORTCUTS = {
    "play_pause":    "Space",
    "stop":          "Escape",
    "next":          "Right",
    "prev":          "Left",
    "seek_fwd_5":    "Ctrl+Right",
    "seek_bwd_5":    "Ctrl+Left",
    "seek_fwd_60":   "Shift+Right",
    "seek_bwd_60":   "Shift+Left",
    "volume_up":     "Up",
    "volume_down":   "Down",
    "mute":          "M",
    "fullscreen":    "F",
    "next_frame":    "Period",
    "prev_frame":    "Comma",
    "speed_up":      "Ctrl+Up",
    "speed_down":    "Ctrl+Down",
    "speed_reset":   "Ctrl+0",
    "open_file":     "Ctrl+O",
    "save_playlist": "Ctrl+S",
    "close":         "Ctrl+Q",
}

SHORTCUT_LABELS = {
    "play_pause":    "Lecture / Pause",
    "stop":          "Arrêt",
    "next":          "Morceau/Vidéo suivant",
    "prev":          "Morceau/Vidéo précédent",
    "seek_fwd_5":    "Avancer de 5 secondes",
    "seek_bwd_5":    "Reculer de 5 secondes",
    "seek_fwd_60":   "Avancer de 60 secondes",
    "seek_bwd_60":   "Reculer de 60 secondes",
    "volume_up":     "Volume +",
    "volume_down":   "Volume -",
    "mute":          "Muet",
    "fullscreen":    "Plein écran (vidéo)",
    "next_frame":    "Image suivante",
    "prev_frame":    "Image précédente",
    "speed_up":      "Accélérer",
    "speed_down":    "Ralentir",
    "speed_reset":   "Vitesse normale (1x)",
    "open_file":     "Ouvrir un fichier",
    "save_playlist": "Enregistrer la liste",
    "close":         "Quitter",
}

DEFAULT_COLORS = {
    "bg_main":        "#0f0d0a",
    "bg_secondary":   "#1e1a12",
    "bg_list":        "#0c0a07",
    "accent":         "#f5a623",
    "accent_dark":    "#c47d0a",
    "text_primary":   "#e8d5a0",
    "text_secondary": "#a08060",
    "text_muted":     "#5a4a28",
    "border":         "#2a2416",
    "border_bright":  "#3d3420",
    "highlight_bg":   "#2a2008",
    "btn_bg":         "#1e1a12",
}

COLOR_LABELS = {
    "bg_main":        "Arrière-plan principal",
    "bg_secondary":   "Arrière-plan secondaire",
    "bg_list":        "Arrière-plan liste",
    "accent":         "Couleur d'accent",
    "accent_dark":    "Accent foncé",
    "text_primary":   "Texte principal",
    "text_secondary": "Texte secondaire",
    "text_muted":     "Texte atténué",
    "border":         "Bordures",
    "border_bright":  "Bordures visibles",
    "highlight_bg":   "Surbrillance",
    "btn_bg":         "Fond des boutons",
}

DEFAULT_FONT = {
    "family": "Segoe UI",
    "size":   13,
    "mono_family": "Consolas",
    "mono_size":   11,
}


# ── Widget de capture de raccourci ────────────────────────────────────────────

class KeyCaptureEdit(QLineEdit):
    """Champ qui capture la prochaine touche pressée."""

    key_captured = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._capturing = False
        self.setReadOnly(True)
        self.setPlaceholderText("Cliquer pour changer…")
        self.mousePressEvent = self._start_capture
        self.setStyleSheet("""
            QLineEdit {
                background: #1e1a12; border: 1px solid #3d3420;
                color: #e8d5a0; padding: 4px 8px; border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #f5a623; background: #2a2008; color: #f5a623;
            }
        """)

    def _start_capture(self, event):
        self._capturing = True
        self.setText("Appuyez sur une touche…")
        self.setFocus()

    def keyPressEvent(self, event):
        if not self._capturing:
            return
        key = event.key()
        modifiers = event.modifiers()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift,
                   Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return
        combo = QKeySequence(modifiers | key).toString()
        self._capturing = False
        self.setText(combo)
        self.key_captured.emit(combo)
        self.clearFocus()

    def focusOutEvent(self, event):
        self._capturing = False
        super().focusOutEvent(event)


# ── Widget couleur ────────────────────────────────────────────────────────────

class ColorButton(QPushButton):
    color_changed = pyqtSignal(str, str)  # (key, hex_color)

    def __init__(self, key: str, color: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._color = color
        self.setFixedSize(36, 24)
        self._update_style()
        self.clicked.connect(self._pick_color)

    def _update_style(self):
        self.setStyleSheet(
            f"background: {self._color}; border: 1px solid #5a4a28; border-radius: 3px;"
        )

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Choisir une couleur")
        if c.isValid():
            self._color = c.name()
            self._update_style()
            self.color_changed.emit(self._key, self._color)

    def get_color(self) -> str:
        return self._color

    def set_color(self, c: str):
        self._color = c
        self._update_style()


# ── Panneau Raccourcis ────────────────────────────────────────────────────────

class ShortcutsTab(QWidget):
    shortcuts_changed = pyqtSignal(dict)

    def __init__(self, shortcuts: dict, parent=None):
        super().__init__(parent)
        self._shortcuts = dict(shortcuts)
        self._edits: Dict[str, KeyCaptureEdit] = {}
        self._setup_ui()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)

        for row, (key, label) in enumerate(SHORTCUT_LABELS.items()):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #e8d5a0; font-size: 12px;")
            grid.addWidget(lbl, row, 0)

            edit = KeyCaptureEdit()
            edit.setText(self._shortcuts.get(key, DEFAULT_SHORTCUTS.get(key, "")))
            edit.key_captured.connect(lambda combo, k=key: self._on_change(k, combo))
            grid.addWidget(edit, row, 1)

            btn_reset = QPushButton("↺")
            btn_reset.setFixedSize(26, 26)
            btn_reset.setToolTip("Réinitialiser")
            btn_reset.clicked.connect(lambda _, k=key, e=edit: self._reset_one(k, e))
            grid.addWidget(btn_reset, row, 2)

            self._edits[key] = edit

        scroll.setWidget(inner)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        btn_row = QHBoxLayout()
        btn_reset_all = QPushButton("Réinitialiser tout")
        btn_reset_all.clicked.connect(self._reset_all)
        btn_row.addWidget(btn_reset_all)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addWidget(scroll)

    def _on_change(self, key: str, combo: str):
        self._shortcuts[key] = combo
        self.shortcuts_changed.emit(self._shortcuts)

    def _reset_one(self, key: str, edit: KeyCaptureEdit):
        default = DEFAULT_SHORTCUTS.get(key, "")
        edit.setText(default)
        self._shortcuts[key] = default
        self.shortcuts_changed.emit(self._shortcuts)

    def _reset_all(self):
        self._shortcuts = dict(DEFAULT_SHORTCUTS)
        for key, edit in self._edits.items():
            edit.setText(DEFAULT_SHORTCUTS.get(key, ""))
        self.shortcuts_changed.emit(self._shortcuts)

    def get_shortcuts(self) -> dict:
        return dict(self._shortcuts)


# ── Panneau Couleurs ─────────────────────────────────────────────────────────

class ColorsTab(QWidget):
    colors_changed = pyqtSignal(dict)

    def __init__(self, colors: dict, parent=None):
        super().__init__(parent)
        self._colors = dict(colors)
        self._btns: Dict[str, ColorButton] = {}
        self._setup_ui()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(10)

        for row, (key, label) in enumerate(COLOR_LABELS.items()):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #e8d5a0; font-size: 12px;")
            grid.addWidget(lbl, row, 0)

            color = self._colors.get(key, DEFAULT_COLORS.get(key, "#000000"))
            btn = ColorButton(key, color)
            btn.color_changed.connect(self._on_color_change)
            grid.addWidget(btn, row, 1)

            lbl_hex = QLabel(color)
            lbl_hex.setStyleSheet("color: #7a6840; font-family: Consolas; font-size: 11px;")
            lbl_hex.setObjectName(f"hex_{key}")
            grid.addWidget(lbl_hex, row, 2)

            self._btns[key] = btn

        scroll.setWidget(inner)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Couleurs par défaut (jaune-orangé)")
        btn_reset.clicked.connect(self._reset_all)
        btn_row.addWidget(btn_reset)

        btn_preset_dark = QPushButton("Preset : Bleu nuit")
        btn_preset_dark.clicked.connect(self._preset_blue)
        btn_row.addWidget(btn_preset_dark)

        btn_preset_green = QPushButton("Preset : Vert terminal")
        btn_preset_green.clicked.connect(self._preset_green)
        btn_row.addWidget(btn_preset_green)

        presets = {
            "Violet": {
                "bg_main": "#110b18", "bg_secondary": "#21132e", "bg_list": "#0b0710",
                "accent": "#c77dff", "accent_dark": "#7b2cbf", "text_primary": "#f0dcff",
                "text_secondary": "#b892d3", "text_muted": "#725486", "border": "#38204d",
                "border_bright": "#5c3475", "highlight_bg": "#32134d", "btn_bg": "#21132e",
            },
            "Interface claire": {
                "bg_main": "#f4f1ea", "bg_secondary": "#e4dfd4", "bg_list": "#fffdf8",
                "accent": "#b05a00", "accent_dark": "#7a3d00", "text_primary": "#29251f",
                "text_secondary": "#62584d", "text_muted": "#82766a", "border": "#c9c0b3",
                "border_bright": "#a79a8a", "highlight_bg": "#f1d8b5", "btn_bg": "#e4dfd4",
            },
            "Rouge": {
                "bg_main": "#180b0b", "bg_secondary": "#2b1111", "bg_list": "#100606",
                "accent": "#ff5c5c", "accent_dark": "#b51f1f", "text_primary": "#ffe2e2",
                "text_secondary": "#d49a9a", "text_muted": "#865252", "border": "#4c1d1d",
                "border_bright": "#763030", "highlight_bg": "#4a1515", "btn_bg": "#2b1111",
            },
            "Noir": {
                "bg_main": "#050505", "bg_secondary": "#111111", "bg_list": "#000000",
                "accent": "#d0d0d0", "accent_dark": "#777777", "text_primary": "#f2f2f2",
                "text_secondary": "#b0b0b0", "text_muted": "#707070", "border": "#242424",
                "border_bright": "#3b3b3b", "highlight_bg": "#202020", "btn_bg": "#111111",
            },
            "Blanc et noir": {
                "bg_main": "#ffffff", "bg_secondary": "#eeeeee", "bg_list": "#fafafa",
                "accent": "#111111", "accent_dark": "#444444", "text_primary": "#111111",
                "text_secondary": "#444444", "text_muted": "#777777", "border": "#cccccc",
                "border_bright": "#999999", "highlight_bg": "#dddddd", "btn_bg": "#eeeeee",
            },
        }
        for name, preset in presets.items():
            button = QPushButton(f"Preset : {name}")
            button.clicked.connect(lambda _, values=preset: self._apply_preset(values))
            btn_row.addWidget(button)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addWidget(scroll)

    def _on_color_change(self, key: str, color: str):
        self._colors[key] = color
        # Mettre à jour le label hex
        for child in self.findChildren(QLabel, f"hex_{key}"):
            child.setText(color)
        self.colors_changed.emit(self._colors)

    def _apply_preset(self, preset: dict):
        self._colors.update(preset)
        for key, btn in self._btns.items():
            btn.set_color(self._colors.get(key, DEFAULT_COLORS[key]))
            for child in self.findChildren(QLabel, f"hex_{key}"):
                child.setText(self._colors[key])
        self.colors_changed.emit(self._colors)

    def _reset_all(self):
        self._apply_preset(dict(DEFAULT_COLORS))

    def _preset_blue(self):
        self._apply_preset({
            "bg_main": "#080c14", "bg_secondary": "#0d1520",
            "bg_list": "#060a10", "accent": "#4da6ff", "accent_dark": "#1a6abf",
            "text_primary": "#c8dff0", "text_secondary": "#6090b0",
            "text_muted": "#304860", "border": "#1a3050", "border_bright": "#2a4a70",
            "highlight_bg": "#0a2040", "btn_bg": "#0d1520",
        })

    def _preset_green(self):
        self._apply_preset({
            "bg_main": "#030a03", "bg_secondary": "#0a1a0a",
            "bg_list": "#020702", "accent": "#00ff88", "accent_dark": "#008844",
            "text_primary": "#b0ffb0", "text_secondary": "#508050",
            "text_muted": "#204020", "border": "#0a2010", "border_bright": "#184018",
            "highlight_bg": "#053010", "btn_bg": "#0a1a0a",
        })

    def get_colors(self) -> dict:
        return dict(self._colors)


# ── Panneau Polices ───────────────────────────────────────────────────────────

class FontsTab(QWidget):
    font_changed = pyqtSignal(dict)

    def __init__(self, font_cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = dict(font_cfg)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(16)

        # Police principale
        main_grp = QGroupBox("POLICE PRINCIPALE")
        main_layout = QGridLayout(main_grp)

        main_layout.addWidget(QLabel("Famille :"), 0, 0)
        self.cmb_main_family = QFontComboBox()
        self.cmb_main_family.setCurrentFont(
            QFont(self._cfg.get("family", "Segoe UI"))
        )
        self.cmb_main_family.currentFontChanged.connect(
            lambda f: self._update("family", f.family())
        )
        main_layout.addWidget(self.cmb_main_family, 0, 1)

        main_layout.addWidget(QLabel("Taille :"), 1, 0)
        self.spn_main_size = QSpinBox()
        self.spn_main_size.setRange(8, 24)
        self.spn_main_size.setValue(self._cfg.get("size", 13))
        self.spn_main_size.valueChanged.connect(
            lambda v: self._update("size", v)
        )
        main_layout.addWidget(self.spn_main_size, 1, 1)

        # Aperçu
        self.lbl_preview = QLabel("AaBbCcDd 123 — SolarSound")
        self.lbl_preview.setStyleSheet(
            "color: #f5a623; background: #1e1a12; padding: 8px; border-radius: 4px;"
        )
        main_layout.addWidget(self.lbl_preview, 2, 0, 1, 2)

        layout.addWidget(main_grp)

        # Police mono (temps, console, Hz)
        mono_grp = QGroupBox("POLICE MONOSPACE (temps, données)")
        mono_layout = QGridLayout(mono_grp)

        mono_layout.addWidget(QLabel("Famille :"), 0, 0)
        self.cmb_mono_family = QFontComboBox()
        self.cmb_mono_family.setCurrentFont(
            QFont(self._cfg.get("mono_family", "Consolas"))
        )
        self.cmb_mono_family.currentFontChanged.connect(
            lambda f: self._update("mono_family", f.family())
        )
        mono_layout.addWidget(self.cmb_mono_family, 0, 1)

        mono_layout.addWidget(QLabel("Taille :"), 1, 0)
        self.spn_mono_size = QSpinBox()
        self.spn_mono_size.setRange(7, 18)
        self.spn_mono_size.setValue(self._cfg.get("mono_size", 11))
        self.spn_mono_size.valueChanged.connect(
            lambda v: self._update("mono_size", v)
        )
        mono_layout.addWidget(self.spn_mono_size, 1, 1)

        self.lbl_mono_preview = QLabel("0:00:00.000  44100 Hz  5.1  1.00x")
        self.lbl_mono_preview.setStyleSheet(
            "color: #7a6840; background: #1e1a12; padding: 8px; border-radius: 4px;"
        )
        mono_layout.addWidget(self.lbl_mono_preview, 2, 0, 1, 2)

        layout.addWidget(mono_grp)

        btn_reset = QPushButton("Polices par défaut")
        btn_reset.clicked.connect(self._reset)
        layout.addWidget(btn_reset)
        layout.addStretch()

        self._refresh_previews()

    def _update(self, key: str, value):
        self._cfg[key] = value
        self._refresh_previews()
        self.font_changed.emit(self._cfg)

    def _refresh_previews(self):
        fam = self._cfg.get("family", "Segoe UI")
        size = self._cfg.get("size", 13)
        self.lbl_preview.setFont(QFont(fam, size))

        mono_fam = self._cfg.get("mono_family", "Consolas")
        mono_size = self._cfg.get("mono_size", 11)
        self.lbl_mono_preview.setFont(QFont(mono_fam, mono_size))

    def _reset(self):
        self._cfg = dict(DEFAULT_FONT)
        self.cmb_main_family.setCurrentFont(QFont(DEFAULT_FONT["family"]))
        self.spn_main_size.setValue(DEFAULT_FONT["size"])
        self.cmb_mono_family.setCurrentFont(QFont(DEFAULT_FONT["mono_family"]))
        self.spn_mono_size.setValue(DEFAULT_FONT["mono_size"])
        self._refresh_previews()
        self.font_changed.emit(self._cfg)

    def get_font_config(self) -> dict:
        return dict(self._cfg)


class AudioTab(QWidget):
    output_changed = pyqtSignal(object)
    progress_style_changed = pyqtSignal(str)

    def __init__(self, devices: list, selected_device=None, progress_style="classic", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        group = QGroupBox("SORTIE AUDIO")
        group_layout = QGridLayout(group)
        group_layout.addWidget(QLabel("Périphérique :"), 0, 0)
        self.cmb_output = QComboBox()
        self.cmb_output.addItem("Automatique (5.1 si disponible)", None)
        for device_id, name, channels in devices:
            self.cmb_output.addItem(f"{name} ({channels} canaux)", device_id)
        selected_index = self.cmb_output.findData(selected_device)
        self.cmb_output.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self.cmb_output.currentIndexChanged.connect(self._on_output_changed)
        group_layout.addWidget(self.cmb_output, 0, 1)
        group_layout.addWidget(QLabel("Barre de lecture :"), 1, 0)
        self.cmb_progress = QComboBox()
        self.cmb_progress.addItem("Classique", "classic")
        self.cmb_progress.addItem("Intensité selon le temps", "intensity")
        self.cmb_progress.addItem("Intensité centrée et fine", "intensity_centered")
        self.cmb_progress.setCurrentIndex(max(0, self.cmb_progress.findData(progress_style)))
        self.cmb_progress.currentIndexChanged.connect(
            lambda index: self.progress_style_changed.emit(self.cmb_progress.itemData(index))
        )
        group_layout.addWidget(self.cmb_progress, 1, 1)
        layout.addWidget(group)
        layout.addStretch()

    def _on_output_changed(self, index: int):
        self.output_changed.emit(self.cmb_output.itemData(index))

    def get_output_device(self):
        return self.cmb_output.currentData()

    def get_progress_style(self):
        return self.cmb_progress.currentData()


# ── Panneau Paramètres complet ────────────────────────────────────────────────

class SettingsPanel(QWidget):
    """Panneau de paramètres avec onglets audio, raccourcis, couleurs et polices."""

    output_changed = pyqtSignal(object)
    progress_style_changed = pyqtSignal(str)
    shortcuts_changed = pyqtSignal(dict)
    colors_changed    = pyqtSignal(dict)
    font_changed      = pyqtSignal(dict)

    def __init__(self, shortcuts: dict = None, colors: dict = None,
                 font_cfg: dict = None, output_devices: list = None,
                 output_device=None, progress_style="classic", parent=None):
        super().__init__(parent)
        shortcuts = shortcuts or dict(DEFAULT_SHORTCUTS)
        colors    = colors    or dict(DEFAULT_COLORS)
        font_cfg  = font_cfg  or dict(DEFAULT_FONT)

        self._setup_ui(shortcuts, colors, font_cfg, output_devices or [], output_device, progress_style)

    def _setup_ui(self, shortcuts, colors, font_cfg, output_devices, output_device, progress_style):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()

        self.audio_tab = AudioTab(output_devices, output_device, progress_style)
        self.audio_tab.output_changed.connect(self.output_changed)
        self.audio_tab.progress_style_changed.connect(self.progress_style_changed)
        tabs.addTab(self.audio_tab, "🔉  Audio")

        self.shortcuts_tab = ShortcutsTab(shortcuts)
        self.shortcuts_tab.shortcuts_changed.connect(self.shortcuts_changed)
        tabs.addTab(self.shortcuts_tab, "⌨  Raccourcis")

        self.colors_tab = ColorsTab(colors)
        self.colors_tab.colors_changed.connect(self.colors_changed)
        tabs.addTab(self.colors_tab, "🎨  Couleurs")

        self.fonts_tab = FontsTab(font_cfg)
        self.fonts_tab.font_changed.connect(self.font_changed)
        tabs.addTab(self.fonts_tab, "🔤  Polices")

        layout.addWidget(tabs)

    def get_shortcuts(self) -> dict:
        return self.shortcuts_tab.get_shortcuts()

    def get_colors(self) -> dict:
        return self.colors_tab.get_colors()

    def get_font_config(self) -> dict:
        return self.fonts_tab.get_font_config()

    def get_output_device(self):
        return self.audio_tab.get_output_device()

    def get_progress_style(self):
        return self.audio_tab.get_progress_style()

    def apply_all(self, shortcuts: dict, colors: dict, font_cfg: dict):
        """Recharge tout depuis une config sauvegardée."""
        # Shortcuts
        for key, edit in self.shortcuts_tab._edits.items():
            edit.setText(shortcuts.get(key, DEFAULT_SHORTCUTS.get(key, "")))
        self.shortcuts_tab._shortcuts = dict(shortcuts)

        # Colors
        self.colors_tab._apply_preset(colors)

        # Fonts
        self.fonts_tab._cfg = dict(font_cfg)
        from PyQt6.QtGui import QFont
        self.fonts_tab.cmb_main_family.setCurrentFont(
            QFont(font_cfg.get("family", "Segoe UI"))
        )
        self.fonts_tab.spn_main_size.setValue(font_cfg.get("size", 13))
        self.fonts_tab.cmb_mono_family.setCurrentFont(
            QFont(font_cfg.get("mono_family", "Consolas"))
        )
        self.fonts_tab.spn_mono_size.setValue(font_cfg.get("mono_size", 11))
        self.fonts_tab._refresh_previews()


# ── Génération du stylesheet depuis une config couleurs + polices ─────────────

def build_stylesheet(colors: dict, font_cfg: dict) -> str:
    """Génère un QSS complet depuis les couleurs et polices choisies."""
    c = {**DEFAULT_COLORS, **colors}
    f = {**DEFAULT_FONT, **font_cfg}
    accent_hover = QColor(c['accent']).lighter(115).name()

    return f"""
QWidget {{
    background-color: {c['bg_main']};
    color: {c['text_primary']};
    font-family: '{f['family']}', 'Segoe UI', sans-serif;
    font-size: {f['size']}px;
}}
QMainWindow {{ background-color: {c['bg_main']}; }}
QPushButton {{
    background-color: {c['btn_bg']};
    color: {c['text_primary']};
    border: 1px solid {c['border_bright']};
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover {{
    background-color: {c['bg_secondary']};
    border-color: {c['accent']};
    color: {c['accent']};
}}
QPushButton:pressed {{
    background-color: {c['accent']};
    color: {c['bg_main']};
}}
QPushButton:checked {{
    background-color: {c['accent_dark']};
    border-color: {c['accent']};
    color: {c['bg_main']};
    font-weight: bold;
}}
QPushButton#btn_play {{
    background-color: {c['accent']};
    color: {c['bg_main']};
    border-radius: 24px;
    font-size: 20px;
    font-weight: bold;
    min-width: 48px; min-height: 48px;
    max-width: 48px; max-height: 48px;
}}
QPushButton#btn_play:hover {{ background-color: {accent_hover}; }}
QPushButton#btn_prev, QPushButton#btn_next, QPushButton#btn_stop {{
    background-color: {c['btn_bg']};
    color: {c['accent']};
    border-radius: 18px;
    font-size: 16px;
    min-width: 36px; min-height: 36px;
    max-width: 36px; max-height: 36px;
    border: 1px solid {c['border']};
}}
QSlider::groove:horizontal {{
    border: none; height: 4px;
    background-color: {c['bg_secondary']}; border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {c['accent']}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background-color: {c['accent']};
    border: 2px solid {c['bg_main']};
    width: 14px; height: 14px;
    margin: -5px 0; border-radius: 7px;
}}
QSlider::groove:vertical {{
    border: none; width: 4px;
    background-color: {c['bg_secondary']}; border-radius: 2px;
}}
QSlider::sub-page:vertical {{
    background: {c['accent']}; border-radius: 2px;
}}
QSlider::handle:vertical {{
    background-color: {c['accent']};
    border: 2px solid {c['bg_main']};
    width: 14px; height: 14px;
    margin: 0 -5px; border-radius: 7px;
}}
QListWidget {{
    background-color: {c['bg_list']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    color: {c['text_primary']};
    outline: none;
}}
QListWidget::item {{
    padding: 8px 12px;
    border-bottom: 1px solid {c['bg_secondary']};
}}
QListWidget::item:selected {{
    background-color: {c['highlight_bg']};
    color: {c['accent']};
    border-left: 3px solid {c['accent']};
}}
QListWidget::item:hover {{ background-color: {c['bg_secondary']}; }}
QGroupBox {{
    border: 1px solid {c['border']};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    color: {c['accent']};
    font-weight: bold; font-size: 12px;
    letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {c['accent']};
    background-color: {c['bg_main']};
}}
QLabel {{ color: {c['text_primary']}; }}
QLabel#title_label {{ color: {c['accent']}; }}
QLabel#sound_label {{ color: {c['text_primary']}; }}
QLabel#subtitle_label {{ color: {c['text_muted']}; }}
QLabel#track_title {{ font-size: 17px; font-weight: bold; color: {c['accent']}; }}
QLabel#track_artist {{ font-size: 13px; color: {c['text_secondary']}; }}
QLabel#time_label {{
    font-family: '{f['mono_family']}', Consolas;
    font-size: {f['mono_size']}px;
    color: {c['text_muted']};
}}
QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: 0 8px 8px 8px;
    background-color: {c['bg_main']};
}}
QTabBar::tab {{
    background-color: {c['bg_list']};
    color: {c['text_muted']};
    border: 1px solid {c['border']};
    padding: 8px 16px;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {c['bg_main']};
    color: {c['accent']};
}}
QTabBar::tab:hover {{ background-color: {c['bg_secondary']}; color: {c['text_primary']}; }}
QScrollBar:vertical {{
    background-color: {c['bg_list']}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background-color: {c['border_bright']}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background-color: {c['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{
    background-color: {c['bg_list']}; height: 8px; border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background-color: {c['border_bright']}; border-radius: 4px; min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background-color: {c['accent']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
QDoubleSpinBox, QSpinBox {{
    background-color: {c['btn_bg']};
    border: 1px solid {c['border_bright']};
    border-radius: 4px; color: {c['text_primary']}; padding: 3px 6px;
}}
QDoubleSpinBox:focus, QSpinBox:focus {{ border-color: {c['accent']}; }}
QComboBox {{
    background-color: {c['btn_bg']}; border: 1px solid {c['border_bright']};
    border-radius: 4px; color: {c['text_primary']}; padding: 4px 8px;
}}
QComboBox:hover {{ border-color: {c['accent']}; }}
QComboBox QAbstractItemView {{
    background-color: {c['btn_bg']}; border: 1px solid {c['border_bright']};
    color: {c['text_primary']};
    selection-background-color: {c['highlight_bg']};
    selection-color: {c['accent']};
}}
QCheckBox {{ color: {c['text_primary']}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {c['border_bright']}; border-radius: 3px;
    background-color: {c['btn_bg']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['accent']}; border-color: {c['accent']};
}}
QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}
QFrame[frameShape="4"], QFrame[frameShape="5"] {{ color: {c['border']}; }}
QMenuBar {{
    background-color: {c['bg_list']}; color: {c['text_primary']};
    border-bottom: 1px solid {c['border']};
}}
QMenuBar::item {{ padding: 6px 12px; }}
QMenuBar::item:selected {{ background-color: {c['bg_secondary']}; color: {c['accent']}; }}
QMenu {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border_bright']}; color: {c['text_primary']};
}}
QMenu::item:selected {{ background-color: {c['highlight_bg']}; color: {c['accent']}; }}
QMenu::separator {{
    height: 1px; background-color: {c['border_bright']}; margin: 4px 8px;
}}
QStatusBar {{
    background-color: {c['bg_list']}; color: {c['text_muted']};
    border-top: 1px solid {c['border']}; font-size: 11px;
}}
QToolTip {{
    background-color: {c['bg_secondary']}; color: {c['accent']};
    border: 1px solid {c['accent']}; border-radius: 4px; padding: 4px 8px;
    font-size: 11px;
}}
QLineEdit {{
    background-color: {c['btn_bg']}; border: 1px solid {c['border_bright']};
    border-radius: 4px; color: {c['text_primary']}; padding: 4px 8px;
}}
QLineEdit:focus {{ border-color: {c['accent']}; }}
"""
