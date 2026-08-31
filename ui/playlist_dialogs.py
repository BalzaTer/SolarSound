"""Dialogs réutilisables pour la gestion des playlists personnalisées"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QDialogButtonBox, QWidget,
    QRadioButton, QButtonGroup
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
import os

try:
    from ..core.custom_playlist import MoodEnum
except (ImportError, ModuleNotFoundError):
    from core.custom_playlist import MoodEnum


MOOD_ICONS = {
    MoodEnum.TRISTE.value: "😢",
    MoodEnum.MOTIVATION.value: "💪",
    MoodEnum.FOCUS.value: "🎯",
    MoodEnum.CHILL.value: "😌",
    MoodEnum.SOIREE.value: "🎉",
    MoodEnum.FLOW.value: "🌊",
}


class MoodChipsWidget(QWidget):
    """Zone de sélection d'humeurs sous forme de boutons à bascule (chips)"""

    def __init__(self, selected_moods=None, parent=None):
        super().__init__(parent)
        selected_moods = selected_moods or []
        self._buttons = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for mood in MoodEnum.get_all_moods():
            icon = MOOD_ICONS.get(mood, "")
            btn = QPushButton(f"{icon} {mood}")
            btn.setCheckable(True)
            btn.setChecked(mood in selected_moods)
            layout.addWidget(btn)
            self._buttons[mood] = btn

        layout.addStretch()

    def selected_moods(self):
        """Retourne la liste des humeurs actuellement cochées"""
        return [mood for mood, btn in self._buttons.items() if btn.isChecked()]

    def set_selected_moods(self, moods):
        moods = moods or []
        for mood, btn in self._buttons.items():
            btn.setChecked(mood in moods)


class MoodTagsDialog(QDialog):
    """Dialog autonome pour sélectionner des humeurs (ex : filtrage rapide)"""

    def __init__(self, selected_moods=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner des humeurs")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Choisissez une ou plusieurs humeurs :"))
        self.chips = MoodChipsWidget(selected_moods, self)
        layout.addWidget(self.chips)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_moods(self):
        return self.chips.selected_moods()


class PlaylistDialog(QDialog):
    """Dialog de création / édition d'une playlist personnalisée"""

    def __init__(self, name="", moods=None, cover_path=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Playlist personnalisée")
        self.setMinimumWidth(420)
        self._cover_source_path = None  # Chemin du fichier image choisi (à importer)
        self._existing_cover_path = cover_path  # Cover déjà enregistrée (nom fichier)

        layout = QVBoxLayout(self)

        # ── Nom ──────────────────────────────────────────────────────
        layout.addWidget(QLabel("Nom de la playlist :"))
        self.edit_name = QLineEdit(name)
        self.edit_name.setPlaceholderText("Ma playlist")
        layout.addWidget(self.edit_name)

        # ── Cover ────────────────────────────────────────────────────
        cover_row = QHBoxLayout()
        self.lbl_cover_preview = QLabel()
        self.lbl_cover_preview.setFixedSize(64, 64)
        self.lbl_cover_preview.setStyleSheet(
            "border: 1px solid #5a4a28; background: rgba(0,0,0,0.15);"
        )
        self.lbl_cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cover_preview.setText("🖼")
        cover_row.addWidget(self.lbl_cover_preview)

        self.btn_choose_cover = QPushButton("Choisir une image…")
        self.btn_choose_cover.clicked.connect(self._on_choose_cover)
        cover_row.addWidget(self.btn_choose_cover)
        cover_row.addStretch()
        layout.addLayout(cover_row)

        # ── Humeurs ──────────────────────────────────────────────────
        layout.addWidget(QLabel("Humeurs associées :"))
        self.chips = MoodChipsWidget(moods, self)
        layout.addWidget(self.chips)

        # ── Boutons ──────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_choose_cover(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image de couverture",
            "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self._cover_source_path = path
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    64, 64,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.lbl_cover_preview.setPixmap(scaled)
                self.lbl_cover_preview.setText("")

    def _on_accept(self):
        if not self.edit_name.text().strip():
            self.edit_name.setFocus()
            return
        self.accept()

    def result_data(self) -> dict:
        """Retourne les données saisies : name, moods, cover_source_path (ou None)"""
        return {
            "name": self.edit_name.text().strip(),
            "moods": self.chips.selected_moods(),
            "cover_source_path": self._cover_source_path,
        }


class PlaylistActionDialog(QDialog):
    """Dialog de confirmation pour charger ou ajouter une playlist perso à la lecture"""

    ACTION_REPLACE = "replace"
    ACTION_APPEND = "append"

    def __init__(self, playlist_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Charger la playlist")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f'Que faire avec "{playlist_name}" ?'))

        self._group = QButtonGroup(self)
        self.radio_replace = QRadioButton("Remplacer la liste de lecture actuelle et lancer la lecture")
        self.radio_append = QRadioButton("Ajouter à la suite de la liste de lecture actuelle")
        self.radio_replace.setChecked(True)
        self._group.addButton(self.radio_replace)
        self._group.addButton(self.radio_append)
        layout.addWidget(self.radio_replace)
        layout.addWidget(self.radio_append)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def action(self) -> str:
        return self.ACTION_REPLACE if self.radio_replace.isChecked() else self.ACTION_APPEND
