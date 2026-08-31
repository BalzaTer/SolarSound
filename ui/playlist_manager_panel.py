"""Panneau de gestion des playlists personnalisées (onglet "Mes Playlists")"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QMessageBox, QFrame, QSizePolicy,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon
import os

try:
    from .playlist_dialogs import PlaylistDialog, PlaylistActionDialog, MOOD_ICONS
    from ..core.playlist_manager import PlaylistManager
    from ..audio.metadata import format_duration, read_cover_art_data
except (ImportError, ModuleNotFoundError):
    from ui.playlist_dialogs import PlaylistDialog, PlaylistActionDialog, MOOD_ICONS
    from core.playlist_manager import PlaylistManager
    from audio.metadata import format_duration, read_cover_art_data


class ReorderableTrackList(QListWidget):
    """QListWidget dont le glisser-déposer interne signale les réordonnancements"""

    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.order_changed.emit()


class PlaylistManagerPanel(QWidget):
    """Gestionnaire de playlists personnalisées : liste + détails + actions CRUD"""

    # Émis quand l'utilisateur confirme le chargement d'une playlist perso
    # dans la liste de lecture principale : (playlist_id, action="replace"|"append")
    load_requested = pyqtSignal(str, str)

    def __init__(self, manager: PlaylistManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._current_playlist_id = None
        self._setup_ui()
        self._connect_signals()
        self.refresh_playlists()

    # ── UI ──────────────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # ── Colonne gauche : liste des playlists ────────────────────
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel("Mes playlists"))

        self.list_playlists = QListWidget()
        self.list_playlists.setIconSize(self.list_playlists.iconSize())
        left_col.addWidget(self.list_playlists)

        left_buttons = QHBoxLayout()
        self.btn_new = QPushButton("＋ Nouvelle")
        self.btn_delete = QPushButton("🗑 Supprimer")
        left_buttons.addWidget(self.btn_new)
        left_buttons.addWidget(self.btn_delete)
        left_col.addLayout(left_buttons)

        left_container = QWidget()
        left_container.setLayout(left_col)
        left_container.setMaximumWidth(280)
        layout.addWidget(left_container)

        # ── Séparateur vertical ──────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(sep)

        # ── Colonne droite : détails + actions ──────────────────────
        right_col = QVBoxLayout()

        header_row = QHBoxLayout()
        self.lbl_cover = QLabel()
        self.lbl_cover.setFixedSize(80, 80)
        self.lbl_cover.setStyleSheet(
            "border: 1px solid #5a4a28; background: rgba(0,0,0,0.15);"
        )
        self.lbl_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cover.setText("🖼")
        header_row.addWidget(self.lbl_cover)

        info_col = QVBoxLayout()
        self.lbl_name = QLabel("—")
        self.lbl_name.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.lbl_moods = QLabel("")
        self.lbl_track_count = QLabel("")
        info_col.addWidget(self.lbl_name)
        info_col.addWidget(self.lbl_moods)
        info_col.addWidget(self.lbl_track_count)
        info_col.addStretch()
        header_row.addLayout(info_col)
        header_row.addStretch()
        right_col.addLayout(header_row)

        actions_row = QHBoxLayout()
        self.btn_edit = QPushButton("✎ Éditer")
        self.btn_add_files = QPushButton("＋ Fichiers")
        self.btn_add_folder = QPushButton("📁 Dossier")
        self.btn_load = QPushButton("▶ Charger")
        actions_row.addWidget(self.btn_edit)
        actions_row.addWidget(self.btn_add_files)
        actions_row.addWidget(self.btn_add_folder)
        actions_row.addStretch()
        actions_row.addWidget(self.btn_load)
        right_col.addLayout(actions_row)

        tracks_toolbar = QHBoxLayout()
        tracks_toolbar.addWidget(QLabel("Pistes (glisser pour réordonner) :"))
        tracks_toolbar.addStretch()
        self.btn_remove_track = QPushButton("✕ Retirer la piste")
        self.btn_remove_track.setToolTip("Retirer la piste sélectionnée de la playlist")
        tracks_toolbar.addWidget(self.btn_remove_track)
        right_col.addLayout(tracks_toolbar)

        self.list_tracks = ReorderableTrackList()
        right_col.addWidget(self.list_tracks)

        right_container = QWidget()
        right_container.setLayout(right_col)
        layout.addWidget(right_container)

        self._set_details_enabled(False)

    def _connect_signals(self):
        self.list_playlists.currentRowChanged.connect(self._on_selection_changed)
        self.btn_new.clicked.connect(self._on_new)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_add_files.clicked.connect(self._on_add_files)
        self.btn_add_folder.clicked.connect(self._on_add_folder)
        self.btn_load.clicked.connect(self._on_load)
        self.btn_remove_track.clicked.connect(self._on_remove_track)
        self.list_tracks.order_changed.connect(self._on_tracks_reordered)

    def _set_details_enabled(self, enabled: bool):
        for w in (self.btn_edit, self.btn_add_files, self.btn_add_folder, self.btn_load):
            w.setEnabled(enabled)

    # ── Rafraîchissement ──────────────────────────────────────────────
    def refresh_playlists(self):
        """Recharge la liste des playlists depuis le manager"""
        previous_id = self._current_playlist_id
        self.list_playlists.clear()

        playlists = self.manager.get_all_playlists()
        restore_row = -1
        for i, playlist in enumerate(playlists):
            item = QListWidgetItem(playlist.name or "(Sans nom)")
            item.setData(Qt.ItemDataRole.UserRole, playlist.id)
            icon = self._cover_icon(playlist)
            if icon:
                item.setIcon(icon)
            self.list_playlists.addItem(item)
            if playlist.id == previous_id:
                restore_row = i

        if restore_row >= 0:
            self.list_playlists.setCurrentRow(restore_row)
        elif self.list_playlists.count() > 0:
            self.list_playlists.setCurrentRow(0)
        else:
            self._current_playlist_id = None
            self._refresh_details(None)

    def _cover_icon(self, playlist):
        """
        Retourne une icône de cover pour la playlist :
        - la cover dédiée si elle existe,
        - sinon la pochette embarquée dans la première piste qui en a une.
        """
        if playlist.cover_path:
            pixmap = self.manager.cover_handler.load_cover_pixmap(playlist.cover_path)
            if pixmap and not pixmap.isNull():
                return QIcon(pixmap)

        for track in playlist.tracks:
            cover_data = read_cover_art_data(track.path)
            if cover_data:
                pixmap = QPixmap()
                if pixmap.loadFromData(cover_data):
                    return QIcon(pixmap)

        return None

    def _on_selection_changed(self, row: int):
        item = self.list_playlists.item(row)
        playlist_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._current_playlist_id = playlist_id
        playlist = self.manager.get_playlist(playlist_id) if playlist_id else None
        self._refresh_details(playlist)

    def _refresh_details(self, playlist):
        self.list_tracks.clear()
        if not playlist:
            self.lbl_name.setText("—")
            self.lbl_moods.setText("")
            self.lbl_track_count.setText("")
            self.lbl_cover.setPixmap(QPixmap())
            self.lbl_cover.setText("🖼")
            self._set_details_enabled(False)
            return

        self._set_details_enabled(True)
        self.lbl_name.setText(playlist.name or "(Sans nom)")
        moods_text = "  ".join(f"{MOOD_ICONS.get(m, '')} {m}" for m in playlist.moods)
        self.lbl_moods.setText(moods_text or "Aucune humeur associée")

        total_duration = sum(t.duration or 0.0 for t in playlist.tracks)
        n = len(playlist.tracks)
        self.lbl_track_count.setText(
            f"{n} piste{'s' if n > 1 else ''} · {format_duration(total_duration)}"
        )

        icon = self._cover_icon(playlist)
        if icon:
            self.lbl_cover.setPixmap(icon.pixmap(80, 80))
            self.lbl_cover.setText("")
        else:
            self.lbl_cover.setPixmap(QPixmap())
            self.lbl_cover.setText("🖼")

        for i, track in enumerate(playlist.tracks):
            dur = format_duration(track.duration) if track.duration else "--:--"
            artist_part = f" — {track.artist}" if track.artist else ""
            item = QListWidgetItem(f"{track.title}{artist_part}   {dur}")
            item.setToolTip(track.path)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list_tracks.addItem(item)

    # ── Actions CRUD ────────────────────────────────────────────────
    def _on_new(self):
        dialog = PlaylistDialog(parent=self)
        if dialog.exec():
            data = dialog.result_data()
            if not data["name"]:
                return
            playlist = self.manager.create_playlist(data["name"], data["moods"])
            if data["cover_source_path"]:
                self._apply_cover(playlist.id, data["cover_source_path"])
            self.refresh_playlists()
            self._select_playlist_id(playlist.id)

    def _on_edit(self):
        playlist = self._get_current_playlist()
        if not playlist:
            return
        dialog = PlaylistDialog(
            name=playlist.name, moods=playlist.moods, cover_path=playlist.cover_path,
            parent=self,
        )
        if dialog.exec():
            data = dialog.result_data()
            if not data["name"]:
                return
            self.manager.update_playlist(playlist.id, name=data["name"], moods=data["moods"])
            if data["cover_source_path"]:
                self._apply_cover(playlist.id, data["cover_source_path"])
            self.refresh_playlists()
            self._select_playlist_id(playlist.id)

    def _apply_cover(self, playlist_id: str, source_path: str):
        cover_name = f"{playlist_id}.jpg"
        saved = self.manager.cover_handler.import_cover_from_file(source_path, cover_name)
        if saved:
            self.manager.update_playlist(playlist_id, cover_path=saved)

    def _on_delete(self):
        playlist = self._get_current_playlist()
        if not playlist:
            return
        reply = QMessageBox.question(
            self, "Supprimer la playlist",
            f'Voulez-vous vraiment supprimer "{playlist.name}" ?\n'
            "Les fichiers audio ne seront pas supprimés, seule la playlist le sera.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.delete_playlist(playlist.id)
            self.refresh_playlists()

    def _on_add_files(self):
        playlist = self._get_current_playlist()
        if not playlist:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Ajouter des fichiers à la playlist",
            "", "Fichiers média (*.mp3 *.wav *.flac *.ogg *.opus *.aiff *.aif *.au *.mp4 *.mkv *.avi *.mov *.wmv *.m4v *.flv *.webm);;Tous (*.*)"
        )
        if paths:
            self.manager.add_tracks_to_playlist(playlist.id, paths)
            self._refresh_details(self.manager.get_playlist(playlist.id))

    def _on_add_folder(self):
        playlist = self._get_current_playlist()
        if not playlist:
            return
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if folder:
            self.manager.add_folder_to_playlist(playlist.id, folder)
            self._refresh_details(self.manager.get_playlist(playlist.id))

    def _on_load(self):
        playlist = self._get_current_playlist()
        if not playlist:
            return
        if not playlist.tracks:
            QMessageBox.information(self, "Playlist vide", "Cette playlist ne contient aucune piste.")
            return
        dialog = PlaylistActionDialog(playlist.name, parent=self)
        if dialog.exec():
            self.load_requested.emit(playlist.id, dialog.action())

    def _on_remove_track(self):
        playlist = self._get_current_playlist()
        if not playlist:
            return
        item = self.list_tracks.currentItem()
        if item is None:
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        self.manager.remove_track_from_playlist(playlist.id, index)
        self._refresh_details(self.manager.get_playlist(playlist.id))

    def _on_tracks_reordered(self):
        """Persiste le nouvel ordre après un glisser-déposer dans la liste des pistes."""
        playlist = self._get_current_playlist()
        if not playlist:
            return
        new_order = [
            self.list_tracks.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_tracks.count())
        ]
        self.manager.reorder_playlist_tracks(playlist.id, new_order)
        # Resynchronise les index UserRole avec le nouvel ordre enregistré
        self._refresh_details(self.manager.get_playlist(playlist.id))

    # ── Helpers ───────────────────────────────────────────────────────
    def _get_current_playlist(self):
        if not self._current_playlist_id:
            return None
        return self.manager.get_playlist(self._current_playlist_id)

    def _select_playlist_id(self, playlist_id: str):
        for i in range(self.list_playlists.count()):
            item = self.list_playlists.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == playlist_id:
                self.list_playlists.setCurrentRow(i)
                return

    def set_theme_colors(self, colors: dict):
        """Réservé pour une future intégration du theming (appelé par MainWindow)"""
        pass
