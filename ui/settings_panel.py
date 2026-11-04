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
    QCheckBox, QDoubleSpinBox, QSlider, QSizePolicy, QListWidget, QFileDialog,
    QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPalette, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

try:
    from ..core.i18n import tr, tr_tab, LANGUAGES, get_language, set_language
except (ImportError, ModuleNotFoundError):
    from core.i18n import tr, tr_tab, LANGUAGES, get_language, set_language


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
    "open_cd":       "Ctrl+Shift+D",
    "scan_missing":  "Ctrl+Shift+R",
    "tab_equalizer": "Ctrl+E",
    "tab_my_playlists": "Ctrl+P",
    "tab_playlist":  "Ctrl+L",
    "tab_video":     "Ctrl+M",
    "tab_surround":  "Ctrl+S",
    "tab_rotation":  "Ctrl+T",
    "tab_vinyl":     "Ctrl+I",
    "tab_settings":  "Ctrl+Shift+P",
    "close":         "Ctrl+Q",
}
CUSTOM_COLOR_PRESET_NAME = "Personnalisé"

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
    "open_cd":       "Ouvrir un CD audio",
    "scan_missing":  "Rechercher les fichiers manquants",
    "tab_equalizer": "Onglet Egaliseur",
    "tab_my_playlists": "Onglet Mes Playlists",
    "tab_playlist":  "Onglet Playlist",
    "tab_video":     "Onglet Video",
    "tab_surround":  "Onglet 5.1",
    "tab_rotation":  "Onglet Rotation",
    "tab_vinyl":     "Onglet Vinyle",
    "tab_settings":  "Onglet Parametres",
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

DEFAULT_COLOR_PRESETS = {
    "Défaut": dict(DEFAULT_COLORS),
    "Bleu nuit": {
        "bg_main": "#080c14", "bg_secondary": "#0d1520", "bg_list": "#060a10",
        "accent": "#4da6ff", "accent_dark": "#1a6abf", "text_primary": "#c8dff0",
        "text_secondary": "#6090b0", "text_muted": "#304860", "border": "#1a3050",
        "border_bright": "#2a4a70", "highlight_bg": "#0a2040", "btn_bg": "#0d1520",
    },
    "Vert terminal": {
        "bg_main": "#030a03", "bg_secondary": "#0a1a0a", "bg_list": "#020702",
        "accent": "#00ff88", "accent_dark": "#008844", "text_primary": "#b0ffb0",
        "text_secondary": "#508050", "text_muted": "#204020", "border": "#0a2010",
        "border_bright": "#184018", "highlight_bg": "#053010", "btn_bg": "#0a1a0a",
    },
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
        self.setObjectName("shortcut_edit")
        self.setMinimumWidth(190)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Segoe UI", 11))
        self.setPlaceholderText("Cliquer pour changer…")
        self.mousePressEvent = self._start_capture

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


class StartupTab(QWidget):
    """Options de lancement automatique et de lecture au démarrage Windows."""

    startup_changed = pyqtSignal(dict)
    resume_position_changed = pyqtSignal(bool)
    position_save_interval_changed = pyqtSignal(int)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        config = config or {}
        self._config = {
            "enabled": bool(config.get("enabled", False)),
            "mode": config.get("mode", "none"),
            "value": config.get("value", ""),
            "resume_position": bool(config.get("resume_position", True)),
            "position_save_interval_seconds": max(
                1,
                min(30, int(config.get("position_save_interval_seconds", 10))),
            ),
        }
        self._sources = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        resume_group = QGroupBox("À la réouverture de SolarSound")
        resume_layout = QVBoxLayout(resume_group)
        resume_layout.addWidget(QLabel("Reprise de la musique en cours :"))
        self.cmb_resume_position = QComboBox()
        self.cmb_resume_position.addItem(
            "Reprendre à la seconde où je me suis arrêté", True
        )
        self.cmb_resume_position.addItem("Recommencer au début du morceau", False)
        resume_position = bool(self._config.get("resume_position", True))
        resume_index = self.cmb_resume_position.findData(resume_position)
        self.cmb_resume_position.setCurrentIndex(max(0, resume_index))
        self.cmb_resume_position.currentIndexChanged.connect(
            self._on_resume_position_changed
        )
        resume_layout.addWidget(self.cmb_resume_position)
        resume_layout.addWidget(QLabel("Enregistrer la position toutes les :"))
        self.spn_position_save_interval = QSpinBox()
        self.spn_position_save_interval.setRange(1, 30)
        self.spn_position_save_interval.setSuffix(" s")
        self.spn_position_save_interval.setValue(
            self._config["position_save_interval_seconds"]
        )
        self.spn_position_save_interval.valueChanged.connect(
            self._on_position_save_interval_changed
        )
        resume_layout.addWidget(self.spn_position_save_interval)
        layout.addWidget(resume_group)

        self.chk_enabled = QCheckBox("Lancer SolarSound au démarrage de Windows")
        self.chk_enabled.setChecked(self._config["enabled"])
        self.chk_enabled.toggled.connect(self._emit_changed)
        layout.addWidget(self.chk_enabled)

        layout.addWidget(QLabel("Lecture automatique :"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Ne rien lancer", "none")
        self.cmb_mode.addItem("Jouer une humeur", "mood")
        self.cmb_mode.addItem("Jouer une playlist", "playlist")
        self.cmb_mode.addItem("Jouer un dossier de playlists", "playlist_folder")
        self.cmb_mode.addItem("Jouer un dossier complet", "filesystem_folder")
        self.cmb_mode.currentIndexChanged.connect(self._refresh_targets)
        layout.addWidget(self.cmb_mode)

        self.cmb_target = QComboBox()
        layout.addWidget(self.cmb_target)

        self.path_row = QWidget()
        path_layout = QHBoxLayout(self.path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Dossier à jouer…")
        self.path_edit.textChanged.connect(self._emit_changed)
        path_layout.addWidget(self.path_edit)
        self.btn_browse = QPushButton("Parcourir…")
        self.btn_browse.clicked.connect(self._browse_folder)
        path_layout.addWidget(self.btn_browse)
        layout.addWidget(self.path_row)
        layout.addStretch()
        self._set_mode(self._config["mode"])

    def set_sources(self, moods, playlists, folders):
        self._sources = {
            "mood": [(name, name) for name in moods],
            "playlist": [(name, playlist_id) for name, playlist_id in playlists],
            "playlist_folder": [(name, folder_id) for name, folder_id in folders],
        }
        self._refresh_targets()

    def _set_mode(self, mode):
        index = self.cmb_mode.findData(mode)
        self.cmb_mode.setCurrentIndex(index if index >= 0 else 0)

    def _refresh_targets(self):
        mode = self.cmb_mode.currentData()
        self.cmb_target.blockSignals(True)
        self.cmb_target.clear()
        for label, value in self._sources.get(mode, []):
            self.cmb_target.addItem(label, value)
        index = self.cmb_target.findData(self._config.get("value", ""))
        if index >= 0:
            self.cmb_target.setCurrentIndex(index)
        self.cmb_target.blockSignals(False)
        self.cmb_target.setVisible(mode in self._sources)
        self.path_row.setVisible(mode == "filesystem_folder")
        self._emit_changed()

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choisir le dossier à jouer")
        if path:
            self.path_edit.setText(path)

    def _emit_changed(self):
        mode = self.cmb_mode.currentData() or "none"
        value = self.path_edit.text() if mode == "filesystem_folder" else self.cmb_target.currentData()
        self._config = {
            "enabled": self.chk_enabled.isChecked(),
            "mode": mode,
            "value": value or "",
            "resume_position": bool(
                self.cmb_resume_position.currentData()
            ),
            "position_save_interval_seconds": (
                self.spn_position_save_interval.value()
            ),
        }
        self.startup_changed.emit(dict(self._config))

    def _on_resume_position_changed(self, index: int):
        self.resume_position_changed.emit(
            bool(self.cmb_resume_position.itemData(index))
        )

    def _on_position_save_interval_changed(self, interval: int):
        self._config["position_save_interval_seconds"] = interval
        self.position_save_interval_changed.emit(interval)


# ── Panneau Couleurs ─────────────────────────────────────────────────────────

class ColorsTab(QWidget):
    colors_changed = pyqtSignal(dict)
    presets_changed = pyqtSignal(dict)

    def __init__(self, colors: dict, presets: dict = None, parent=None):
        super().__init__(parent)
        self._colors = {**DEFAULT_COLORS, **colors}
        self._presets = {
            name: {**DEFAULT_COLORS, **values}
            for name, values in DEFAULT_COLOR_PRESETS.items()
        }
        if isinstance(presets, dict):
            for name, values in presets.items():
                if (
                    isinstance(name, str)
                    and name.strip()
                    and name.casefold() != "défaut"
                    and isinstance(values, dict)
                ):
                    self._presets[name] = {**DEFAULT_COLORS, **values}
        self._presets["Défaut"] = dict(DEFAULT_COLORS)
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
        self.cmb_presets = QComboBox()
        self.cmb_presets.addItems(self._presets)
        self.cmb_presets.currentTextChanged.connect(self._update_preset_controls)
        btn_row.addWidget(self.cmb_presets, 1)

        self.btn_apply_preset = QPushButton("Appliquer")
        self.btn_apply_preset.clicked.connect(self._apply_selected_preset)
        btn_row.addWidget(self.btn_apply_preset)

        self.btn_save_preset = QPushButton("Enregistrer")
        self.btn_save_preset.setToolTip("Enregistrer les couleurs dans le preset sélectionné")
        self.btn_save_preset.clicked.connect(self._save_preset)
        btn_row.addWidget(self.btn_save_preset)

        self.btn_save_preset_as = QPushButton("Enregistrer sous…")
        self.btn_save_preset_as.clicked.connect(self._save_preset_as)
        btn_row.addWidget(self.btn_save_preset_as)

        self.btn_delete_preset = QPushButton("Supprimer")
        self.btn_delete_preset.clicked.connect(self._delete_preset)
        btn_row.addWidget(self.btn_delete_preset)

        layout.addLayout(btn_row)
        layout.addWidget(scroll)
        self._select_preset_for_colors()
        self._update_preset_controls()

    def _on_color_change(self, key: str, color: str):
        self._colors[key] = color
        # Mettre à jour le label hex
        for child in self.findChildren(QLabel, f"hex_{key}"):
            child.setText(color)
        self.colors_changed.emit(self._colors)

    def _apply_preset(self, preset: dict):
        self._colors = {**DEFAULT_COLORS, **preset}
        for key, btn in self._btns.items():
            btn.set_color(self._colors.get(key, DEFAULT_COLORS[key]))
            for child in self.findChildren(QLabel, f"hex_{key}"):
                child.setText(self._colors[key])
        self._select_preset_for_colors()
        self._update_preset_controls()
        self.colors_changed.emit(self._colors)

    def _apply_selected_preset(self):
        name = self.cmb_presets.currentText()
        if name in self._presets:
            self._apply_preset(self._presets[name])

    def _reset_all(self):
        self.cmb_presets.setCurrentText("Défaut")
        self._apply_selected_preset()

    def _select_preset_for_colors(self):
        for name, values in self._presets.items():
            if values == self._colors:
                self.cmb_presets.setCurrentText(name)
                return
        if self.cmb_presets.findText(CUSTOM_COLOR_PRESET_NAME) < 0:
            self.cmb_presets.addItem(CUSTOM_COLOR_PRESET_NAME)
        self.cmb_presets.setCurrentText(CUSTOM_COLOR_PRESET_NAME)

    def _update_preset_controls(self, *_):
        name = self.cmb_presets.currentText()
        is_saved = name in self._presets
        is_default = name == "Défaut"
        self.btn_apply_preset.setEnabled(is_saved)
        self.btn_save_preset.setEnabled(is_saved and not is_default)
        self.btn_delete_preset.setEnabled(is_saved and not is_default)

    def _save_preset(self):
        name = self.cmb_presets.currentText()
        if name == "Défaut" or name not in self._presets:
            return
        self._presets[name] = dict(self._colors)
        self.presets_changed.emit(self.get_presets())

    def _save_preset_as(self):
        name, accepted = QInputDialog.getText(self, "Nouveau preset", "Nom du preset :")
        if not accepted:
            return
        name = name.strip()
        if not name or name.casefold() in (
            "défaut",
            CUSTOM_COLOR_PRESET_NAME.casefold(),
        ):
            QMessageBox.warning(self, "Nom invalide", "Ce nom de preset n'est pas autorisé.")
            return

        existing = next((saved for saved in self._presets if saved.casefold() == name.casefold()), None)
        if existing:
            answer = QMessageBox.question(
                self,
                "Remplacer le preset",
                f"Le preset « {existing} » existe déjà. Voulez-vous le remplacer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            name = existing

        self._presets[name] = dict(self._colors)
        self.cmb_presets.blockSignals(True)
        self.cmb_presets.clear()
        self.cmb_presets.addItems(self._presets)
        self.cmb_presets.setCurrentText(name)
        self.cmb_presets.blockSignals(False)
        self._update_preset_controls()
        self.presets_changed.emit(self.get_presets())

    def _delete_preset(self):
        name = self.cmb_presets.currentText()
        if name == "Défaut" or name not in self._presets:
            return
        answer = QMessageBox.question(
            self,
            "Supprimer le preset",
            f"Supprimer le preset « {name} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        del self._presets[name]
        self.cmb_presets.blockSignals(True)
        self.cmb_presets.clear()
        self.cmb_presets.addItems(self._presets)
        self.cmb_presets.setCurrentText("Défaut")
        self.cmb_presets.blockSignals(False)
        self._update_preset_controls()
        self._apply_selected_preset()
        self.presets_changed.emit(self.get_presets())

    def get_colors(self) -> dict:
        return dict(self._colors)

    def get_presets(self) -> dict:
        return {name: dict(colors) for name, colors in self._presets.items()}

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
    normalizer_changed = pyqtSignal(dict)

    def __init__(self, devices: list, selected_device=None, progress_style="classic",
                 parent=None, normalizer_config=None):
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

        normalizer_config = normalizer_config or {}
        self.chk_normalizer = QCheckBox("Activer la normalisation du niveau sonore")
        self.chk_normalizer.setChecked(bool(normalizer_config.get("enabled", False)))
        self.chk_normalizer.setToolTip(
            "Ajuste le niveau moyen de chaque fichier audio pour réduire les "
            "écarts de volume entre les morceaux."
        )
        self.sld_normalizer_strength = QSlider(Qt.Orientation.Horizontal)
        self.sld_normalizer_strength.setRange(0, 100)
        self.sld_normalizer_strength.setSingleStep(5)
        try:
            normalizer_strength = int(normalizer_config.get("strength", 50))
        except (TypeError, ValueError):
            normalizer_strength = 50
        self.sld_normalizer_strength.setValue(
            max(0, min(100, normalizer_strength))
        )
        self.lbl_normalizer_strength = QLabel()
        self.lbl_normalizer_strength.setMinimumWidth(42)
        self._update_normalizer_strength_label(
            self.sld_normalizer_strength.value()
        )
        normalizer_group = QGroupBox("NORMALISEUR")
        normalizer_layout = QGridLayout(normalizer_group)
        normalizer_layout.addWidget(self.chk_normalizer, 0, 0, 1, 3)
        normalizer_layout.addWidget(QLabel("Puissance :"), 1, 0)
        normalizer_layout.addWidget(self.sld_normalizer_strength, 1, 1)
        normalizer_layout.addWidget(self.lbl_normalizer_strength, 1, 2)
        normalizer_layout.addWidget(
            QLabel(
                "À 100 %, vise un niveau moyen de -18 dBFS, avec une hausse "
                "limitée à +12 dB et les crêtes source plafonnées à -1 dBFS."
            ),
            2, 0, 1, 3,
        )
        layout.addWidget(normalizer_group)
        self.sld_normalizer_strength.setEnabled(self.chk_normalizer.isChecked())
        self.chk_normalizer.toggled.connect(self._on_normalizer_changed)
        self.sld_normalizer_strength.valueChanged.connect(
            self._on_normalizer_strength_changed
        )
        layout.addStretch()

    def _on_output_changed(self, index: int):
        self.output_changed.emit(self.cmb_output.itemData(index))

    def get_output_device(self):
        return self.cmb_output.currentData()

    def get_progress_style(self):
        return self.cmb_progress.currentData()

    def get_normalizer_config(self) -> dict:
        return {
            "enabled": self.chk_normalizer.isChecked(),
            "strength": self.sld_normalizer_strength.value(),
        }

    def _update_normalizer_strength_label(self, strength: int):
        self.lbl_normalizer_strength.setText(f"{strength} %")

    def _on_normalizer_strength_changed(self, strength: int):
        self._update_normalizer_strength_label(strength)
        self._on_normalizer_changed()

    def _on_normalizer_changed(self, _checked=False):
        enabled = self.chk_normalizer.isChecked()
        self.sld_normalizer_strength.setEnabled(enabled)
        self.normalizer_changed.emit(self.get_normalizer_config())


# ── Panneau Paramètres complet ────────────────────────────────────────────────

class LibraryTab(QWidget):
    """
    Dossiers de musique locaux : utilisés pour élargir la recherche aux
    fichiers non encore ajoutés à une playlist, et pour retrouver les pistes
    déplacées/renommées dans l'onglet "Mes Playlists".
    """

    folders_changed = pyqtSignal(list)
    refresh_requested = pyqtSignal()
    bpm_analysis_requested = pyqtSignal()

    def __init__(self, folders: list = None, parent=None):
        super().__init__(parent)
        folders = folders or []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        group = QGroupBox("DOSSIERS DE MUSIQUE")
        group_layout = QVBoxLayout(group)

        hint = QLabel(
            "Ces dossiers sont utilisés pour élargir la recherche aux "
            "fichiers non encore ajoutés à une playlist, et pour retrouver "
            "les pistes déplacées ou renommées depuis l'onglet \"Mes Playlists\"."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 11px; color: #7a6a48;")
        group_layout.addWidget(hint)

        self.list_folders = QListWidget()
        self.list_folders.addItems(folders)
        group_layout.addWidget(self.list_folders)

        buttons_row = QHBoxLayout()
        self.btn_add = QPushButton("＋ Ajouter un dossier")
        self.btn_remove = QPushButton("－ Retirer")
        self.btn_refresh = QPushButton()
        self.btn_refresh.setFixedSize(32, 32)
        self.btn_refresh.setIconSize(QSize(20, 20))
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "icons",
            "rotation.svg",
        )
        self.btn_refresh.setIcon(QIcon(icon_path))
        self.btn_refresh.setToolTip("Rafraîchir et réindexer les dossiers")
        self.btn_refresh.setAccessibleName("Rafraîchir et réindexer les dossiers")
        self.btn_analyze_bpm = QPushButton(" Analyser et inscrire les BPM")
        buttons_row.addWidget(self.btn_add)
        buttons_row.addWidget(self.btn_remove)
        buttons_row.addWidget(self.btn_analyze_bpm)
        buttons_row.addWidget(self.btn_refresh)
        group_layout.addLayout(buttons_row)

        layout.addWidget(group)
        layout.addStretch()

        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_refresh.clicked.connect(self.refresh_requested)
        self.btn_analyze_bpm.clicked.connect(self.bpm_analysis_requested)

    def _on_add(self):
        folder = QFileDialog.getExistingDirectory(self, "Choisir un dossier de musique")
        if folder:
            existing = self.get_folders()
            if folder not in existing:
                self.list_folders.addItem(folder)
                self.folders_changed.emit(self.get_folders())

    def _on_remove(self):
        row = self.list_folders.currentRow()
        if row >= 0:
            self.list_folders.takeItem(row)
            self.folders_changed.emit(self.get_folders())

    def get_folders(self) -> list:
        return [self.list_folders.item(i).text() for i in range(self.list_folders.count())]

    def set_folders(self, folders: list):
        self.list_folders.clear()
        self.list_folders.addItems(folders or [])

    def set_indexing(self, indexing: bool):
        self.list_folders.setEnabled(not indexing)
        self.btn_add.setEnabled(not indexing)
        self.btn_remove.setEnabled(not indexing)
        self.btn_refresh.setEnabled(not indexing)


class LanguageTab(QWidget):
    """Choix de la langue de l'interface."""

    language_changed = pyqtSignal(str)

    def __init__(self, current_language: str = "fr", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self.lbl = QLabel(tr("settings.language.label"))
        row.addWidget(self.lbl)

        self.combo = QComboBox()
        self._codes = list(LANGUAGES.keys())
        for code in self._codes:
            self.combo.addItem(LANGUAGES[code], code)
        if current_language in self._codes:
            self.combo.setCurrentIndex(self._codes.index(current_language))
        row.addWidget(self.combo)
        row.addStretch()
        layout.addLayout(row)

        self.lbl_notice = QLabel(tr("settings.language.restart_notice"))
        self.lbl_notice.setStyleSheet("color: gray; font-size: 11px;")
        self.lbl_notice.setWordWrap(True)
        layout.addWidget(self.lbl_notice)
        layout.addStretch()

        self.combo.currentIndexChanged.connect(self._on_changed)

    def _on_changed(self, index: int):
        if 0 <= index < len(self._codes):
            self.language_changed.emit(self._codes[index])

    def get_language(self) -> str:
        idx = self.combo.currentIndex()
        return self._codes[idx] if 0 <= idx < len(self._codes) else "fr"

    def retranslate(self):
        self.lbl.setText(tr("settings.language.label"))
        self.lbl_notice.setText(tr("settings.language.restart_notice"))


class ShuffleTab(QWidget):
    """Onglet de configuration du shuffle intelligent."""
    
    smart_shuffle_config_changed = pyqtSignal(dict)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = dict(config)
        self._setup_ui()
        self._update_from_config()

    def _setup_ui(self):
        """Initialise l'interface utilisateur."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Mode principal
        mode_group = QGroupBox(tr("settings.shuffle.mode.title"))
        mode_layout = QVBoxLayout()
        
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem(tr("settings.shuffle.mode.simple"), "simple")
        self.cmb_mode.addItem(tr("settings.shuffle.mode.intelligent"), "intelligent")
        self.cmb_mode.currentIndexChanged.connect(self._emit_config_changed)
        mode_layout.addWidget(self.cmb_mode)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Paramètres du mode Intelligent
        self.smart_group = QGroupBox(tr("settings.shuffle.smart_settings"))
        smart_layout = QVBoxLayout()
        smart_layout.setSpacing(10)
        
        # Poids des critères
        weights_group = QGroupBox(tr("settings.shuffle.weights"))
        weights_layout = QVBoxLayout()
        
        # BPM Weight
        bpm_layout = QHBoxLayout()
        bpm_layout.addWidget(QLabel(tr("settings.shuffle.bpm_weight")))
        self.slider_bpm_weight = QSlider(Qt.Orientation.Horizontal)
        self.slider_bpm_weight.setRange(0, 100)
        self.slider_bpm_weight.valueChanged.connect(self._on_weight_changed)
        self.lbl_bpm_weight = QLabel("50%")
        self.lbl_bpm_weight.setFixedWidth(40)
        self.lbl_bpm_weight.setAlignment(Qt.AlignmentFlag.AlignRight)
        bpm_layout.addWidget(self.slider_bpm_weight)
        bpm_layout.addWidget(self.lbl_bpm_weight)
        weights_layout.addLayout(bpm_layout)
        
        # Energy Weight
        energy_layout = QHBoxLayout()
        energy_layout.addWidget(QLabel(tr("settings.shuffle.energy_weight")))
        self.slider_energy_weight = QSlider(Qt.Orientation.Horizontal)
        self.slider_energy_weight.setRange(0, 100)
        self.slider_energy_weight.valueChanged.connect(self._on_weight_changed)
        self.lbl_energy_weight = QLabel("30%")
        self.lbl_energy_weight.setFixedWidth(40)
        self.lbl_energy_weight.setAlignment(Qt.AlignmentFlag.AlignRight)
        energy_layout.addWidget(self.slider_energy_weight)
        energy_layout.addWidget(self.lbl_energy_weight)
        weights_layout.addLayout(energy_layout)
        
        # Volume Weight
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel(tr("settings.shuffle.volume_weight")))
        self.slider_volume_weight = QSlider(Qt.Orientation.Horizontal)
        self.slider_volume_weight.setRange(0, 100)
        self.slider_volume_weight.valueChanged.connect(self._on_weight_changed)
        self.lbl_volume_weight = QLabel("20%")
        self.lbl_volume_weight.setFixedWidth(40)
        self.lbl_volume_weight.setAlignment(Qt.AlignmentFlag.AlignRight)
        volume_layout.addWidget(self.slider_volume_weight)
        volume_layout.addWidget(self.lbl_volume_weight)
        weights_layout.addLayout(volume_layout)
        
        weights_group.setLayout(weights_layout)
        smart_layout.addWidget(weights_group)
        
        # Tolérances
        tolerances_group = QGroupBox(tr("settings.shuffle.tolerances"))
        tolerances_layout = QVBoxLayout()
        
        # BPM Tolerance
        bpm_tol_layout = QHBoxLayout()
        bpm_tol_layout.addWidget(QLabel(tr("settings.shuffle.bpm_tolerance")))
        self.spn_bpm_tolerance = QDoubleSpinBox()
        self.spn_bpm_tolerance.setRange(0.0, 50.0)
        self.spn_bpm_tolerance.setSingleStep(1.0)
        self.spn_bpm_tolerance.setSuffix(" BPM")
        self.spn_bpm_tolerance.valueChanged.connect(self._emit_config_changed)
        bpm_tol_layout.addWidget(self.spn_bpm_tolerance)
        tolerances_layout.addLayout(bpm_tol_layout)
        
        # Enable BPM Multiples
        self.chk_bpm_multiples = QCheckBox(tr("settings.shuffle.enable_multiples"))
        self.chk_bpm_multiples.setChecked(True)
        self.chk_bpm_multiples.stateChanged.connect(self._emit_config_changed)
        tolerances_layout.addWidget(self.chk_bpm_multiples)
        
        # Energy Tolerance
        energy_tol_layout = QHBoxLayout()
        energy_tol_layout.addWidget(QLabel(tr("settings.shuffle.energy_tolerance")))
        self.spn_energy_tolerance = QDoubleSpinBox()
        self.spn_energy_tolerance.setRange(0.0, 1.0)
        self.spn_energy_tolerance.setSingleStep(0.05)
        self.spn_energy_tolerance.valueChanged.connect(self._emit_config_changed)
        energy_tol_layout.addWidget(self.spn_energy_tolerance)
        tolerances_layout.addLayout(energy_tol_layout)
        
        # Volume Tolerance
        volume_tol_layout = QHBoxLayout()
        volume_tol_layout.addWidget(QLabel(tr("settings.shuffle.volume_tolerance")))
        self.spn_volume_tolerance = QDoubleSpinBox()
        self.spn_volume_tolerance.setRange(0.0, 1.0)
        self.spn_volume_tolerance.setSingleStep(0.05)
        self.spn_volume_tolerance.valueChanged.connect(self._emit_config_changed)
        volume_tol_layout.addWidget(self.spn_volume_tolerance)
        tolerances_layout.addLayout(volume_tol_layout)
        
        tolerances_group.setLayout(tolerances_layout)
        smart_layout.addWidget(tolerances_group)
        
        # Premier morceau
        first_track_group = QGroupBox(tr("settings.shuffle.first_track"))
        first_track_layout = QVBoxLayout()
        
        # Min Duration
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel(tr("settings.shuffle.min_duration")))
        self.spn_first_track_duration = QSpinBox()
        self.spn_first_track_duration.setRange(0, 300)
        self.spn_first_track_duration.setSuffix(" " + tr("settings.shuffle.seconds"))
        self.spn_first_track_duration.valueChanged.connect(self._emit_config_changed)
        duration_layout.addWidget(self.spn_first_track_duration)
        first_track_layout.addLayout(duration_layout)
        
        # Selection Method
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel(tr("settings.shuffle.selection_method")))
        self.cmb_first_track_selection = QComboBox()
        self.cmb_first_track_selection.addItems([
            tr("settings.shuffle.random"),
            tr("settings.shuffle.high_energy"),
            tr("settings.shuffle.low_energy"),
            tr("settings.shuffle.balanced")
        ])
        self.cmb_first_track_selection.currentIndexChanged.connect(self._emit_config_changed)
        selection_layout.addWidget(self.cmb_first_track_selection)
        first_track_layout.addLayout(selection_layout)
        
        first_track_group.setLayout(first_track_layout)
        smart_layout.addWidget(first_track_group)
        
        # Aléatoire contrôlé
        randomness_group = QGroupBox(tr("settings.shuffle.randomness"))
        randomness_layout = QVBoxLayout()
        
        randomness_hint = QLabel(tr("settings.shuffle.randomness_hint"))
        randomness_hint.setWordWrap(True)
        randomness_hint.setStyleSheet("color: #888;")
        randomness_layout.addWidget(randomness_hint)
        
        randomness_slider_layout = QHBoxLayout()
        randomness_slider_layout.addWidget(QLabel(tr("settings.shuffle.randomness_level")))
        self.slider_randomness = QSlider(Qt.Orientation.Horizontal)
        self.slider_randomness.setRange(0, 100)
        self.slider_randomness.valueChanged.connect(self._on_randomness_changed)
        self.lbl_randomness = QLabel("30%")
        self.lbl_randomness.setFixedWidth(40)
        self.lbl_randomness.setAlignment(Qt.AlignmentFlag.AlignRight)
        randomness_slider_layout.addWidget(self.slider_randomness)
        randomness_slider_layout.addWidget(self.lbl_randomness)
        randomness_layout.addLayout(randomness_slider_layout)
        
        randomness_group.setLayout(randomness_layout)
        smart_layout.addWidget(randomness_group)
        
        # Cache
        cache_layout = QHBoxLayout()
        self.chk_enable_cache = QCheckBox(tr("settings.shuffle.enable_cache"))
        self.chk_enable_cache.setChecked(True)
        self.chk_enable_cache.stateChanged.connect(self._emit_config_changed)
        cache_layout.addWidget(self.chk_enable_cache)
        cache_layout.addStretch()
        smart_layout.addLayout(cache_layout)
        
        self.smart_group.setLayout(smart_layout)
        layout.addWidget(self.smart_group)
        
        # Boutons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        btn_reset = QPushButton(tr("settings.reset"))
        btn_reset.clicked.connect(self._reset_to_defaults)
        buttons_layout.addWidget(btn_reset)
        
        layout.addLayout(buttons_layout)
        
        scroll.setWidget(inner)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _update_from_config(self):
        """Met à jour l'UI depuis la configuration."""
        # Mode
        mode = self._config.get("mode", "simple")
        for i in range(self.cmb_mode.count()):
            if self.cmb_mode.itemData(i) == mode:
                self.cmb_mode.setCurrentIndex(i)
                break
        
        # Poids
        self.slider_bpm_weight.setValue(self._config.get("bpm_weight", 50))
        self.slider_energy_weight.setValue(self._config.get("energy_weight", 30))
        self.slider_volume_weight.setValue(self._config.get("volume_weight", 20))
        self._update_weight_labels()
        
        # Tolérances
        self.spn_bpm_tolerance.setValue(self._config.get("bpm_tolerance", 5.0))
        self.chk_bpm_multiples.setChecked(self._config.get("enable_bpm_multiples", True))
        self.spn_energy_tolerance.setValue(self._config.get("energy_tolerance", 0.1))
        self.spn_volume_tolerance.setValue(self._config.get("volume_tolerance", 0.1))
        
        # Premier morceau
        self.spn_first_track_duration.setValue(int(self._config.get("first_track_min_duration", 30.0)))
        selection_methods = ["random", "high_energy", "low_energy", "balanced"]
        selection_translations = [
            tr("settings.shuffle.random"),
            tr("settings.shuffle.high_energy"),
            tr("settings.shuffle.low_energy"),
            tr("settings.shuffle.balanced")
        ]
        current_method = self._config.get("first_track_selection", "balanced")
        for i, method in enumerate(selection_methods):
            if method == current_method:
                self.cmb_first_track_selection.setCurrentIndex(i)
                break
        
        # Aléatoire
        self.slider_randomness.setValue(int(self._config.get("randomness_factor", 0.3) * 100))
        self._update_randomness_label()
        
        # Cache
        self.chk_enable_cache.setChecked(self._config.get("enable_cache", True))
        
        # Activer/désactiver les paramètres intelligents
        self._update_smart_params_enabled()

    def _on_weight_changed(self):
        """Gère le changement des poids."""
        self._config["bpm_weight"] = self.slider_bpm_weight.value()
        self._config["energy_weight"] = self.slider_energy_weight.value()
        self._config["volume_weight"] = self.slider_volume_weight.value()
        
        # Normaliser pour que la somme fasse 100
        total = self._config["bpm_weight"] + self._config["energy_weight"] + self._config["volume_weight"]
        if total > 0 and total != 100:
            # Ajuster automatiquement le plus grand
            max_key = max(["bpm_weight", "energy_weight", "volume_weight"], 
                         key=lambda k: self._config[k])
            self._config[max_key] += 100 - total
            getattr(self, f"slider_{max_key}").setValue(self._config[max_key])
        
        self._update_weight_labels()
        self._emit_config_changed()

    def _update_weight_labels(self):
        """Met à jour les labels des poids."""
        self.lbl_bpm_weight.setText(f"{self.slider_bpm_weight.value()}%")
        self.lbl_energy_weight.setText(f"{self.slider_energy_weight.value()}%")
        self.lbl_volume_weight.setText(f"{self.slider_volume_weight.value()}%")

    def _on_randomness_changed(self):
        """Gère le changement du facteur d'aléatoire."""
        self._config["randomness_factor"] = self.slider_randomness.value() / 100.0
        self._update_randomness_label()
        self._emit_config_changed()

    def _update_randomness_label(self):
        """Met à jour le label du facteur d'aléatoire."""
        self.lbl_randomness.setText(f"{self.slider_randomness.value()}%")

    def _emit_config_changed(self):
        """Émet le signal de changement de configuration."""
        self.smart_shuffle_config_changed.emit(self._config)

    def _update_smart_params_enabled(self):
        """Active/désactive les paramètres selon le mode."""
        is_intelligent = self._config.get("mode", "simple") == "intelligent"
        self.smart_group.setEnabled(is_intelligent)

    def _reset_to_defaults(self):
        """Réinitialise aux valeurs par défaut."""
        from ..core.smart_shuffle_config import SmartShuffleConfig
        default_config = SmartShuffleConfig.default()
        self._config = default_config.to_dict()
        self._update_from_config()
        self._emit_config_changed()

    def get_config(self) -> dict:
        """Retourne la configuration actuelle."""
        return self._config

    def set_config(self, config: dict):
        """Définit une nouvelle configuration."""
        self._config = dict(config)
        self._update_from_config()

    def retranslate(self):
        """Met à jour les textes pour la langue actuelle."""
        # Reconstruire l'UI pour mettre à jour les traductions
        old_config = self._config.copy()
        self._setup_ui()
        self._config = old_config
        self._update_from_config()


class SettingsPanel(QWidget):
    """Panneau de paramètres avec onglets audio, raccourcis, couleurs et polices."""

    output_changed = pyqtSignal(object)
    progress_style_changed = pyqtSignal(str)
    shortcuts_changed = pyqtSignal(dict)
    colors_changed    = pyqtSignal(dict)
    color_presets_changed = pyqtSignal(dict)
    font_changed      = pyqtSignal(dict)
    folders_changed   = pyqtSignal(list)
    language_changed  = pyqtSignal(str)
    startup_changed   = pyqtSignal(dict)
    resume_position_changed = pyqtSignal(bool)
    position_save_interval_changed = pyqtSignal(int)
    normalizer_changed = pyqtSignal(dict)
    library_refresh_requested = pyqtSignal()
    library_bpm_analysis_requested = pyqtSignal()
    smart_shuffle_config_changed = pyqtSignal(dict)

    def __init__(self, shortcuts: dict = None, colors: dict = None,
                 font_cfg: dict = None, output_devices: list = None,
                 output_device=None, progress_style="classic",
                 library_folders: list = None, language: str = "fr",
                 startup_config: dict = None, parent=None, color_presets: dict = None,
                 normalizer_config: dict = None, smart_shuffle_config: dict = None):
        super().__init__(parent)
        shortcuts = shortcuts or dict(DEFAULT_SHORTCUTS)
        colors    = colors    or dict(DEFAULT_COLORS)
        font_cfg  = font_cfg  or dict(DEFAULT_FONT)
        smart_shuffle_config = smart_shuffle_config or {}

        self._setup_ui(shortcuts, colors, font_cfg, output_devices or [], output_device,
                    progress_style, library_folders or [], language,
                    startup_config or {}, color_presets or {},
                    normalizer_config or {}, smart_shuffle_config)

    def _setup_ui(self, shortcuts, colors, font_cfg, output_devices, output_device,
                progress_style, library_folders, language, startup_config,
                color_presets, normalizer_config, smart_shuffle_config):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        tabs = self._tabs

        self.audio_tab = AudioTab(
            output_devices, output_device, progress_style,
            normalizer_config=normalizer_config,
        )
        self.audio_tab.output_changed.connect(self.output_changed)
        self.audio_tab.progress_style_changed.connect(self.progress_style_changed)
        self.audio_tab.normalizer_changed.connect(self.normalizer_changed)
        tabs.addTab(self.audio_tab, tr_tab("settings.tab.audio"))

        self.shortcuts_tab = ShortcutsTab(shortcuts)
        self.shortcuts_tab.shortcuts_changed.connect(self.shortcuts_changed)
        tabs.addTab(self.shortcuts_tab, tr_tab("settings.tab.shortcuts"))

        self.startup_tab = StartupTab(startup_config)
        self.startup_tab.startup_changed.connect(self.startup_changed)
        self.startup_tab.resume_position_changed.connect(
            self.resume_position_changed
        )
        self.startup_tab.position_save_interval_changed.connect(
            self.position_save_interval_changed
        )
        tabs.addTab(self.startup_tab, "Démarrage")

        self.colors_tab = ColorsTab(colors, color_presets)
        self.colors_tab.colors_changed.connect(self.colors_changed)
        self.colors_tab.presets_changed.connect(self.color_presets_changed)
        tabs.addTab(self.colors_tab, tr_tab("settings.tab.colors"))

        self.fonts_tab = FontsTab(font_cfg)
        self.fonts_tab.font_changed.connect(self.font_changed)
        tabs.addTab(self.fonts_tab, tr_tab("settings.tab.fonts"))

        self.library_tab = LibraryTab(library_folders)
        self.library_tab.folders_changed.connect(self.folders_changed)
        self.library_tab.refresh_requested.connect(self.library_refresh_requested)
        self.library_tab.bpm_analysis_requested.connect(
            self.library_bpm_analysis_requested
        )
        tabs.addTab(self.library_tab, tr_tab("settings.tab.library"))

        self.shuffle_tab = ShuffleTab(smart_shuffle_config)
        self.shuffle_tab.smart_shuffle_config_changed.connect(self.smart_shuffle_config_changed)
        tabs.addTab(self.shuffle_tab, tr_tab("settings.tab.shuffle"))

        self.language_tab = LanguageTab(language)
        self.language_tab.language_changed.connect(self.language_changed)
        tabs.addTab(self.language_tab, tr_tab("settings.tab.language"))

        layout.addWidget(tabs)
        tabs.setIconSize(QSize(18, 18))
        self.set_theme_colors(colors)

    def _tinted_tab_icon(self, name: str, color: str) -> QIcon:
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "icons",
            name,
        )
        if not os.path.isfile(icon_path):
            return QIcon()
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        QSvgRenderer(icon_path).render(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
        painter.end()
        return QIcon(pixmap)

    def set_theme_colors(self, colors: dict):
        """Met à jour la teinte des icônes des onglets de paramètres."""
        accent = colors.get("accent", DEFAULT_COLORS["accent"])
        tab_icons = (
            (self.audio_tab, "surround.svg"),
            (self.shortcuts_tab, "raccourcis.svg"),
            (self.startup_tab, "demarrage.svg"),
            (self.colors_tab, "palette.svg"),
            (self.fonts_tab, "police.svg"),
            (self.library_tab, "dossier.svg"),
            (self.shuffle_tab, "aleatoire.svg"),
            (self.language_tab, "langue.svg"),
        )
        for index, (widget, icon_name) in enumerate(tab_icons):
            self._tabs.setTabIcon(index, self._tinted_tab_icon(icon_name, accent))
        self.library_tab.btn_refresh.setIcon(
            self._tinted_tab_icon("rotation.svg", accent)
        )

    def retranslate_ui(self):
        """Remet à jour les textes de ce panneau après un changement de langue à chaud."""
        self._tabs.setTabText(0, tr_tab("settings.tab.audio"))
        self._tabs.setTabText(1, tr_tab("settings.tab.shortcuts"))
        self._tabs.setTabText(2, "Démarrage")
        self._tabs.setTabText(3, tr_tab("settings.tab.colors"))
        self._tabs.setTabText(4, tr_tab("settings.tab.fonts"))
        self._tabs.setTabText(5, tr_tab("settings.tab.library"))
        self._tabs.setTabText(6, tr_tab("settings.tab.shuffle"))
        self._tabs.setTabText(7, tr_tab("settings.tab.language"))
        self.language_tab.retranslate()
        self.shuffle_tab.retranslate()

    def get_shortcuts(self) -> dict:
        return self.shortcuts_tab.get_shortcuts()

    def get_colors(self) -> dict:
        return self.colors_tab.get_colors()

    def get_color_presets(self) -> dict:
        return self.colors_tab.get_presets()
    def get_font_config(self) -> dict:
        return self.fonts_tab.get_font_config()

    def get_output_device(self):
        return self.audio_tab.get_output_device()

    def get_progress_style(self):
        return self.audio_tab.get_progress_style()

    def get_normalizer_config(self) -> dict:
        return self.audio_tab.get_normalizer_config()

    def get_library_folders(self) -> list:
        return self.library_tab.get_folders()

    def set_library_indexing(self, indexing: bool):
        self.library_tab.set_indexing(indexing)

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
QLineEdit#shortcut_edit {{
    background-color: {c['btn_bg']}; border: 1px solid {c['border_bright']};
    color: {c['text_primary']}; padding: 4px 8px; border-radius: 4px;
    font-family: 'Segoe UI', 'Arial', sans-serif; font-size: 12px;
}}
QLineEdit#shortcut_edit:focus {{
    border-color: {c['accent']}; background-color: {c['highlight_bg']};
    color: {c['accent']};
}}
"""
