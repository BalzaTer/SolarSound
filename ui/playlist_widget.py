"""Widget de liste de lecture avec drag & drop"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QInputDialog, QMessageBox,
    QAbstractItemView, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QIcon, QColor, QFont, QAction
import os

try:
    from ..core.playlist import Playlist, Track, PlayMode
    from ..audio.metadata import read_metadata, format_duration
    from ..audio.cd import CdAudio, make_cd_uri
    from ..core.custom_playlist import MoodEnum
except (ImportError, ModuleNotFoundError):
    from core.playlist import Playlist, Track, PlayMode
    from audio.metadata import read_metadata, format_duration
    from audio.cd import CdAudio, make_cd_uri
    from core.custom_playlist import MoodEnum


class PlaylistWidget(QWidget):
    """Panneau de gestion de la liste de lecture"""

    track_activated = pyqtSignal(int)   # index du morceau à jouer
    playlist_changed = pyqtSignal()
    mood_selected = pyqtSignal(str)      # nom de l'humeur cliquée (génère un Flow)
    open_playlist_manager = pyqtSignal()  # demande de bascule vers l'onglet "Mes Playlists"

    def __init__(self, playlist: Playlist, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.playlist = playlist
        self._theme_colors = {}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── Barre d'outils ────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self.btn_add = QPushButton("＋ Ajouter")
        self.btn_add.setToolTip("Ajouter des fichiers à la liste")
        toolbar.addWidget(self.btn_add)

        self.btn_add_folder = QPushButton("📁 Dossier")
        self.btn_add_folder.setToolTip("Ajouter un dossier entier")
        toolbar.addWidget(self.btn_add_folder)

        self.btn_add_cd = QPushButton("💿 CD audio")
        self.btn_add_cd.setToolTip("Ajouter les pistes d'un CD audio")
        toolbar.addWidget(self.btn_add_cd)

        self.btn_remove = QPushButton("✕ Retirer")
        self.btn_remove.setToolTip("Retirer le morceau sélectionné")
        toolbar.addWidget(self.btn_remove)

        toolbar.addStretch()

        self.btn_clear = QPushButton("🗑 Vider")
        self.btn_clear.setToolTip("Vider la liste")
        toolbar.addWidget(self.btn_clear)

        layout.addLayout(toolbar)

        # ── Barre d'infos (nombre de morceaux / durée totale) ──────────
        playlist_bar = QHBoxLayout()
        playlist_bar.setSpacing(4)
        playlist_bar.addStretch()

        self.lbl_count = QLabel("0 morceaux")
        self.lbl_count.setStyleSheet("font-size: 11px; color: #5a4a28;")
        playlist_bar.addWidget(self.lbl_count)

        layout.addLayout(playlist_bar)

        # ── Barre humeurs (accès rapide au Flow des playlists persos) ──
        mood_bar = QHBoxLayout()
        mood_bar.setSpacing(4)

        mood_icons = {
            MoodEnum.TRISTE.value: "😢",
            MoodEnum.MOTIVATION.value: "💪",
            MoodEnum.FOCUS.value: "🎯",
            MoodEnum.CHILL.value: "😌",
            MoodEnum.SOIREE.value: "🎉",
            MoodEnum.FLOW.value: "🌊",
        }
        self.mood_buttons = {}
        for mood in MoodEnum.get_all_moods():
            icon = mood_icons.get(mood, "")
            btn = QPushButton(f"{icon} {mood}")
            btn.setToolTip(f"Générer un mix \"{mood}\" à partir de vos playlists persos")
            btn.clicked.connect(lambda _checked, m=mood: self.mood_selected.emit(m))
            mood_bar.addWidget(btn)
            self.mood_buttons[mood] = btn

        mood_bar.addStretch()

        self.btn_open_playlist_manager = QPushButton("💾 Mes Playlists →")
        self.btn_open_playlist_manager.setToolTip("Gérer vos playlists personnalisées")
        self.btn_open_playlist_manager.clicked.connect(self.open_playlist_manager.emit)
        mood_bar.addWidget(self.btn_open_playlist_manager)

        layout.addLayout(mood_bar)

        # ── Liste ─────────────────────────────────────────────────────
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setAlternatingRowColors(False)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.list_widget)

    def _connect_signals(self):
        self.btn_add.clicked.connect(self._on_add_files)
        self.btn_add_folder.clicked.connect(self._on_add_folder)
        self.btn_add_cd.clicked.connect(self._on_add_cd)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_clear.clicked.connect(self._on_clear)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)

    # ── Gestion des fichiers ──────────────────────────────────────────
    def _on_add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Ajouter des fichiers audio et vidéo",
            "", "Fichiers média (*.mp3 *.wav *.flac *.ogg *.opus *.aiff *.aif *.au *.rf64 *.w64 *.mp4 *.mkv *.avi *.mov *.wmv *.m4v *.flv *.webm);;Audio (*.mp3 *.wav *.flac *.ogg *.opus *.aiff *.aif *.au *.rf64 *.w64);;Vidéo (*.mp4 *.mkv *.avi *.mov *.wmv *.m4v *.flv *.webm);;Tous (*.*)"
        )
        if paths:
            self._add_files(paths)

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier"
        )
        if folder:
            paths = []
            for root, _, files in os.walk(folder):
                for f in sorted(files):
                    ext = f.lower()
                    if any(ext.endswith(e) for e in Playlist.ALL_FORMATS):
                        paths.append(os.path.join(root, f))
            if paths:
                self._add_files(paths)

    def _on_add_cd(self):
        drives = CdAudio.drives()
        if not drives:
            QMessageBox.information(
                self, "CD audio", "Aucun lecteur CD détecté."
            )
            return

        drive, accepted = QInputDialog.getItem(
            self, "Ajouter un CD audio", "Lecteur :", drives, 0, False
        )
        if not accepted:
            return

        cd = CdAudio()
        try:
            track_count = cd.track_count(drive)
            if track_count < 1:
                raise RuntimeError("Le disque ne contient aucune piste audio")
            tracks = []
            for number in range(1, track_count + 1):
                cd.open(drive, number)
                duration = cd.duration
                cd.close()
                track = Track(
                    path=make_cd_uri(drive, number),
                    title=f"Piste {number:02d}",
                    album=f"CD audio ({drive})",
                    duration=duration,
                )
                self.playlist.add_track(track)
                self._add_list_item(track)
                tracks.append(track)
            self._update_count()
            self.playlist_changed.emit()
        except Exception as exc:
            cd.close()
            QMessageBox.critical(self, "CD audio", f"Impossible de lire le CD :\n{exc}")

    # Gestion du glisser-déposer externe (fichiers et dossiers)
    def dragEnterEvent(self, event):
        md: QMimeData = event.mimeData()
        if md.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        md: QMimeData = event.mimeData()
        if not md.hasUrls():
            return
        urls = md.urls()
        paths = []
        for u in urls:
            local = u.toLocalFile()
            if not local:
                continue
            if os.path.isdir(local):
                for root, _, files in os.walk(local):
                    for f in sorted(files):
                        ext = f.lower()
                        if any(ext.endswith(e) for e in Playlist.ALL_FORMATS):
                            paths.append(os.path.join(root, f))
            else:
                paths.append(local)

        if not paths:
            return

        # Si la liste contient un fichier .playlist, charger la première trouvée
        playlist_files = [p for p in paths if p.lower().endswith('.playlist')]
        if playlist_files:
            try:
                self.playlist.load(playlist_files[0])
                self.refresh_from_playlist()
                self.playlist_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Impossible de charger la playlist :\n{e}")
            return

        # Sinon, ajouter les fichiers média valides
        media_paths = [p for p in paths if os.path.splitext(p)[1].lower() in Playlist.ALL_FORMATS]
        if media_paths:
            self._add_files(media_paths)

    def _add_files(self, paths: list):
        for path in paths:
            meta = read_metadata(path)
            track = Track(
                path=path,
                title=meta["title"],
                artist=meta["artist"],
                album=meta["album"],
                duration=meta["duration"],
            )
            self.playlist.add_track(track)
            self._add_list_item(track)
        self._update_count()
        self.playlist_changed.emit()

    def _add_list_item(self, track: Track):
        dur = format_duration(track.duration) if track.duration > 0 else "--:--"
        artist_part = f" — {track.artist}" if track.artist else ""
        text = f"{track.title}{artist_part}"
        sub = f"  {dur}"

        item = QListWidgetItem()
        item.setText(text)
        item.setToolTip(track.path)
        item.setData(Qt.ItemDataRole.UserRole, track.path)
        item.setStatusTip(dur)
        self.list_widget.addItem(item)

    def _on_remove(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)
            self.playlist.remove_track(row)
            self._update_count()
            self.playlist_changed.emit()

    def _on_clear(self):
        if self.playlist.tracks:
            reply = QMessageBox.question(
                self, "Vider la liste",
                "Voulez-vous vraiment vider toute la liste de lecture ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.playlist.clear()
                self.list_widget.clear()
                self._update_count()
                self.playlist_changed.emit()

    def _on_double_click(self, item: QListWidgetItem):
        row = self.list_widget.row(item)
        self.track_activated.emit(row)

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_play = QAction("▶  Lire ce morceau", self)
        act_remove = QAction("✕  Retirer de la liste", self)
        act_explore = QAction("📁  Ouvrir dans l'explorateur", self)

        row = self.list_widget.row(item)
        act_play.triggered.connect(lambda: self.track_activated.emit(row))
        act_remove.triggered.connect(self._on_remove)
        act_explore.triggered.connect(lambda: self._open_in_explorer(item))

        menu.addAction(act_play)
        menu.addSeparator()
        menu.addAction(act_remove)
        menu.addSeparator()
        menu.addAction(act_explore)
        menu.exec(self.list_widget.viewport().mapToGlobal(pos))

    def _open_in_explorer(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            import subprocess
            subprocess.Popen(f'explorer /select,"{path}"', shell=True)

    # ── Playlist files ────────────────────────────────────────────────
    def _on_save_playlist(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer la liste de lecture",
            "", "Listes de lecture (*.playlist)"
        )
        if path:
            if not path.endswith(".playlist"):
                path += ".playlist"
            try:
                self.playlist.save(path)
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Impossible de sauvegarder :\n{e}")

    def _on_load_playlist(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir une liste de lecture",
            "", "Listes de lecture (*.playlist);;Tous (*.*)"
        )
        if path:
            try:
                self.playlist.load(path)
                self.refresh_from_playlist()
                self.playlist_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Impossible de charger :\n{e}")

    # ── Rafraîchissement ──────────────────────────────────────────────
    def refresh_from_playlist(self):
        """Recharge la liste graphique depuis self.playlist"""
        self.list_widget.clear()
        for track in self.playlist.tracks:
            self._add_list_item(track)
        self._update_count()

    def set_active_row(self, index: int):
        """Met en évidence le morceau en cours de lecture"""
        accent = self._theme_colors.get("accent", "#f5a623")
        text_primary = self._theme_colors.get("text_primary", "#e8d5a0")
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if i == index:
                item.setForeground(QColor(accent))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setText("▶ " + item.text().lstrip("▶ "))
            else:
                item.setForeground(QColor(text_primary))
                font = item.font()
                font.setBold(False)
                item.setFont(font)
                t = item.text()
                if t.startswith("▶ "):
                    item.setText(t[2:])
        if 0 <= index < self.list_widget.count():
            self.list_widget.scrollToItem(self.list_widget.item(index))

    def set_theme_colors(self, colors: dict):
        self._theme_colors = dict(colors)
        current_row = self.playlist.current_index
        self.set_active_row(current_row if 0 <= current_row < self.list_widget.count() else -1)

    def _update_count(self):
        n = len(self.playlist)
        dur = format_duration(self.playlist.total_duration)
        self.lbl_count.setText(f"{n} morceau{'x' if n > 1 else ''} · {dur}")
