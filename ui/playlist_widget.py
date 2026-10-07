"""Widget de liste de lecture avec drag & drop"""

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QInputDialog, QMessageBox,
    QAbstractItemView, QMenu, QStyle, QStyleOptionButton
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QMimeData, QThread, QSize, QRectF, QByteArray,
)
from PyQt6.QtGui import (
    QIcon, QColor, QFont, QAction, QPainter, QPixmap,
)
from PyQt6.QtSvg import QSvgRenderer
import os

try:
    from ..core.playlist import Playlist, Track, PlayMode
    from ..audio.metadata import read_metadata, format_duration
    from ..audio.cd import CdAudio, make_cd_uri
    from ..audio.cd_metadata import fetch_release_by_toc, fetch_cover_art, cache_cover_for_drive
    from ..core.custom_playlist import MoodEnum
except (ImportError, ModuleNotFoundError):
    from core.playlist import Playlist, Track, PlayMode
    from audio.metadata import read_metadata, format_duration
    from audio.cd import CdAudio, make_cd_uri
    from audio.cd_metadata import fetch_release_by_toc, fetch_cover_art, cache_cover_for_drive
    from core.custom_playlist import MoodEnum


class CdMetadataWorker(QThread):
    """
    Recherche en arrière-plan les métadonnées (titre/artiste/album/pochette)
    d'un CD inséré, via MusicBrainz, sans bloquer l'interface pendant la
    requête réseau.
    """

    result_ready = pyqtSignal(object, object)  # (dict metadonnées ou None, bytes pochette ou None)

    def __init__(self, toc: dict, parent=None):
        super().__init__(parent)
        self.toc = toc

    def run(self):
        metadata = fetch_release_by_toc(self.toc)
        cover_bytes = None
        if metadata and metadata.get("mbid"):
            cover_bytes = fetch_cover_art(metadata["mbid"])
        self.result_ready.emit(metadata, cover_bytes)


class PlaylistMetadataWorker(QThread):
    result_ready = pyqtSignal(object)
    progress = pyqtSignal(int, int, str)

    def __init__(self, tracks, parent=None):
        super().__init__(parent)
        self.tracks = tuple(tracks)

    def run(self):
        results = []
        for current, track in enumerate(self.tracks, start=1):
            if self.isInterruptionRequested():
                break
            try:
                results.append((track, read_metadata(track.path)))
            except Exception:
                pass
            finally:
                self.progress.emit(current, len(self.tracks), track.path)
        self.result_ready.emit(results)


class FavoriteButton(QPushButton):
    """Bouton cœur à icône vectorielle, centrée dans une zone fixe."""

    def __init__(self, favorite=False, accent="#f5a623", framed=False, parent=None):
        super().__init__(parent)
        self._favorite = favorite
        self._accent = accent
        self._framed = framed
        self._heart_pixmap = QPixmap()
        self.setFixedSize(32, 32)
        if framed:
            self.setStyleSheet("QPushButton { padding: 0; }")
        else:
            self.setStyleSheet(
                "QPushButton {"
                "background: transparent; border: none; padding: 0;"
                "}"
                "QPushButton:hover { background: transparent; border: none; }"
            )
        self.setText("")
        self.setIcon(QIcon())
        self._update_heart()

    def set_favorite(self, favorite: bool):
        self._favorite = favorite
        self._update_heart()
        self.update()

    def set_accent(self, accent: str):
        self._accent = accent
        self._update_heart()
        self.update()

    def _update_heart(self):
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "icons",
            "heart.svg",
        )
        with open(icon_path, "rb") as heart_file:
            svg_data = heart_file.read()

        if not self._favorite:
            original_fill = b"fill:#f5a623;fill-opacity:1;stroke-width:1.50733"
            outline_style = (
                f"fill:none;stroke:{self._accent};stroke-width:4;"
                "stroke-linejoin:round;stroke-linecap:round"
            ).encode("ascii")
            svg_data = svg_data.replace(original_fill, outline_style)

        renderer = QSvgRenderer(QByteArray(svg_data))
        if not renderer.isValid():
            raise ValueError(f"Le fichier SVG du coeur est invalide : {icon_path}")

        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(4, 4, 56, 56))
        if self._favorite:
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceIn
            )
            painter.fillRect(pixmap.rect(), QColor(self._accent))
        painter.end()
        self._heart_pixmap = pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._framed:
            option = QStyleOptionButton()
            option.initFrom(self)
            option.state |= QStyle.StateFlag.State_Raised
            if self.isDown():
                option.state |= QStyle.StateFlag.State_Sunken
            if self.underMouse():
                option.state |= QStyle.StateFlag.State_MouseOver
            self.style().drawControl(
                QStyle.ControlElement.CE_PushButtonBevel,
                option,
                painter,
                self,
            )
        center = QRectF(self.rect()).center()
        icon_rect = QRectF(center.x() - 12, center.y() - 12, 24, 24)
        painter.drawPixmap(icon_rect, self._heart_pixmap, QRectF(0, 0, 64, 64))
        painter.end()


class PlaylistTrackRow(QWidget):
    """Affichage d'une piste avec son bouton de favori."""

    favorite_toggled = pyqtSignal(str)
    track_activated = pyqtSignal()

    def __init__(self, track: Track, favorite: bool, accent: str, parent=None):
        super().__init__(parent)
        self.track = track
        self._favorite = favorite
        self._active = False
        self._accent = accent
        self._text_color = "#e8d5a0"
        self.setMouseTracking(True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background-color: transparent; border: none;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 6, 0)
        layout.setSpacing(4)

        self.lbl_track = QLabel()
        self.lbl_track.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.lbl_track, stretch=1)

        self.btn_favorite = FavoriteButton(
            favorite=favorite, accent=accent, parent=self
        )
        self.btn_favorite.clicked.connect(
            lambda: self.favorite_toggled.emit(self.track.path)
        )
        layout.addWidget(
            self.btn_favorite,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self.set_track(track)
        self.set_favorite(favorite)

    def enterEvent(self, event):
        self.btn_favorite.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.btn_favorite.setVisible(self._favorite)
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.track_activated.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def set_track(self, track: Track):
        self.track = track
        artist_part = f" — {track.artist}" if track.artist else ""
        self._display_name = f"{track.title}{artist_part}"
        self._refresh_track_label()

    def set_favorite(self, favorite: bool):
        self._favorite = favorite
        self.btn_favorite.set_favorite(favorite)
        self.btn_favorite.setToolTip(
            "Retirer des coups de coeur" if favorite else "Ajouter aux coups de coeur"
        )
        self.btn_favorite.setVisible(favorite or self.underMouse())

    def set_active(self, active: bool):
        self._active = active
        self._refresh_track_label()

    def set_theme_colors(self, colors: dict):
        self._accent = colors.get("accent", "#f5a623")
        self._text_color = colors.get("text_primary", "#e8d5a0")
        self.btn_favorite.set_accent(self._accent)
        self._refresh_track_label()

    def _refresh_track_label(self):
        prefix = "▶ " if self._active else ""
        self.lbl_track.setText(prefix + self._display_name)
        self.lbl_track.setStyleSheet(
            "background-color: transparent; border: none;"
            f"color: {self._accent if self._active else self._text_color};"
        )
        font = self.lbl_track.font()
        font.setBold(self._active)
        self.lbl_track.setFont(font)

class PlaylistWidget(QWidget):
    """Panneau de gestion de la liste de lecture"""

    track_activated = pyqtSignal(int)   # index du morceau à jouer
    favorite_toggled = pyqtSignal(str)
    playlist_changed = pyqtSignal()
    mood_selected = pyqtSignal(str)      # nom de l'humeur cliquée (génère un Flow)
    play_favorites_requested = pyqtSignal()
    open_playlist_manager = pyqtSignal()  # demande de bascule vers l'onglet "Mes Playlists"
    restored_track_metadata = pyqtSignal(object)
    import_progress_changed = pyqtSignal(int, int, str)

    def __init__(self, playlist: Playlist, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.playlist = playlist
        self._theme_colors = {}
        self._favorite_paths = set()
        self._cd_metadata_worker = None  # référence gardée le temps de la recherche en ligne
        self._restore_metadata_worker = None
        self._metadata_workers = set()
        self._metadata_progress = {}
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._cancel_restore_metadata)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── Barre d'outils ────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self.btn_add = QPushButton("\u2009Ajouter")
        self.btn_add.setToolTip("Ajouter des fichiers à la liste")
        toolbar.addWidget(self.btn_add)

        self.btn_add_folder = QPushButton("\u2009Dossier")
        self.btn_add_folder.setToolTip("Ajouter un dossier entier")
        toolbar.addWidget(self.btn_add_folder)

        self.btn_add_cd = QPushButton("\u2009CD audio")
        self.btn_add_cd.setToolTip("Ajouter les pistes d'un CD audio")
        toolbar.addWidget(self.btn_add_cd)

        self.btn_remove = QPushButton("\u2009Retirer")
        self.btn_remove.setToolTip("Retirer le morceau sélectionné")
        toolbar.addWidget(self.btn_remove)

        toolbar.addStretch()

        self.btn_clear = QPushButton("\u2009Vider")
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

        self.btn_open_playlist_manager = QPushButton("\u2009Mes Playlists")
        self.btn_open_playlist_manager.setToolTip("Gérer vos playlists personnalisées")
        self.btn_open_playlist_manager.clicked.connect(self.open_playlist_manager.emit)
        mood_bar.addWidget(self.btn_open_playlist_manager)

        self.btn_play_favorites = QPushButton("\u2009Coups de coeur")
        self.btn_play_favorites.setToolTip("Lire la playlist Mes coups de coeur")
        self.btn_play_favorites.clicked.connect(self.play_favorites_requested.emit)
        mood_bar.addWidget(self.btn_play_favorites)
        for button in (
            self.btn_add,
            self.btn_add_folder,
            self.btn_add_cd,
            self.btn_remove,
            self.btn_clear,
            self.btn_open_playlist_manager,
            self.btn_play_favorites,
        ):
            button.setIconSize(QSize(18, 18))

        layout.addLayout(mood_bar)

        # ── Liste ─────────────────────────────────────────────────────
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setAlternatingRowColors(False)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.setMouseTracking(True)
        self.list_widget.setStyleSheet(
            "QListWidget::item { padding: 0px; }"
        )
        self.set_theme_colors(self._theme_colors)
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

            # Recherche automatique des métadonnées (titre/artiste/album/
            # pochette) en ligne, en arrière-plan pour ne pas bloquer
            # l'interface pendant la requête réseau.
            try:
                toc = CdAudio.read_toc(drive)
                self._cd_metadata_worker = CdMetadataWorker(toc, self)
                self._cd_metadata_worker.result_ready.connect(
                    lambda metadata, cover, tracks=tracks, drive=drive:
                        self._on_cd_metadata_ready(tracks, drive, metadata, cover)
                )
                self._cd_metadata_worker.start()
            except Exception as toc_exc:
                print(f"[CD] Lecture du TOC impossible, pas de recherche de métadonnées : {toc_exc}")

        except Exception as exc:
            cd.close()
            QMessageBox.critical(self, "CD audio", f"Impossible de lire le CD :\n{exc}")

    def _on_cd_metadata_ready(self, tracks, drive, metadata, cover_bytes):
        """
        Applique les métadonnées trouvées en ligne pour ce CD (titre par
        piste, artiste, album, pochette), si une correspondance a été
        trouvée sur MusicBrainz. En l'absence de correspondance ou de
        réseau, les titres génériques ("Piste 01"...) sont conservés.
        """
        self._cd_metadata_worker = None

        if cover_bytes:
            cache_cover_for_drive(drive, cover_bytes)

        if not metadata:
            return

        album = metadata.get("album") or ""
        artist = metadata.get("artist") or ""
        mb_tracks = metadata.get("tracks") or []

        for i, track in enumerate(tracks):
            if album:
                track.album = album
            if artist:
                track.artist = artist
            if i < len(mb_tracks) and mb_tracks[i]:
                track.title = mb_tracks[i]
            self._refresh_item_for_path(track.path, track)

        self.playlist_changed.emit()

    def _refresh_item_for_path(self, path: str, track: Track):
        """Met à jour le texte affiché d'une piste déjà présente dans la liste."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self._set_list_item_text(item, track)
                break

    @staticmethod
    def _set_list_item_text(item, track: Track):
        dur = format_duration(track.duration) if track.duration > 0 else "--:--"
        artist_part = f" — {track.artist}" if track.artist else ""
        item.setToolTip(track.path)
        item.setStatusTip(dur)
        list_widget = item.listWidget()
        row = list_widget.itemWidget(item) if list_widget else None
        if isinstance(row, PlaylistTrackRow):
            row.set_track(track)
        else:
            item.setText(f"{track.title}{artist_part}")

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
        tracks = [Track(path=path) for path in paths]
        self.playlist.add_track_batch(tracks)
        for track in tracks:
            self._add_list_item(track)
        self._update_count()
        self.playlist_changed.emit()
        self._start_metadata_worker(tracks)

    def restore_files_async(self, paths: list):
        tracks = [Track(path=path) for path in paths]
        self.playlist.add_track_batch(tracks)
        for track in tracks:
            self._add_list_item(track)

        self._update_count()
        self.playlist_changed.emit()
        if not tracks:
            return

        self._start_metadata_worker(tracks, restored=True)

    def _start_metadata_worker(self, tracks, *, restored=False):
        if not tracks:
            return
        worker = PlaylistMetadataWorker(tracks, self)
        worker.result_ready.connect(self._apply_restored_metadata)
        worker.progress.connect(
            lambda current, total, path, worker=worker:
                self._update_import_progress(worker, current, total, path)
        )
        worker.finished.connect(
            lambda worker=worker: self._clear_restore_metadata_worker(worker)
        )
        self._metadata_workers.add(worker)
        self._metadata_progress[worker] = (0, len(tracks), "")
        self._refresh_import_progress()
        if restored:
            self._restore_metadata_worker = worker
        worker.start()

    def _apply_restored_metadata(self, results):
        active_track_ids = {id(track) for track in self.playlist.tracks}
        items_by_path = {}
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            path = item.data(Qt.ItemDataRole.UserRole)
            items_by_path.setdefault(path, []).append(item)

        current_track = self.playlist.current_track
        current_track_updated = False
        for track, meta in results:
            if id(track) not in active_track_ids:
                continue
            track.title = meta.get("title") or os.path.splitext(os.path.basename(track.path))[0]
            track.artist = meta.get("artist", "")
            track.album = meta.get("album", "")
            track.duration = meta.get("duration", 0.0)
            for item in items_by_path.get(track.path, []):
                self._set_list_item_text(item, track)
            if track is current_track:
                current_track_updated = True

        self._update_count()
        if current_track_updated:
            self.restored_track_metadata.emit(current_track)

    def _clear_restore_metadata_worker(self, worker):
        self._metadata_workers.discard(worker)
        self._metadata_progress.pop(worker, None)
        if self._restore_metadata_worker is worker:
            self._restore_metadata_worker = None
        self._refresh_import_progress()

    def _update_import_progress(self, worker, current, total, path):
        if worker not in self._metadata_progress:
            return
        self._metadata_progress[worker] = (current, total, path)
        self._refresh_import_progress()

    def _refresh_import_progress(self):
        if not self._metadata_progress:
            self.import_progress_changed.emit(0, 0, "")
            return

        current = sum(progress[0] for progress in self._metadata_progress.values())
        total = sum(progress[1] for progress in self._metadata_progress.values())
        active_path = next(
            (
                progress[2]
                for progress in reversed(tuple(self._metadata_progress.values()))
                if progress[2]
            ),
            "",
        )
        self.import_progress_changed.emit(current, total, active_path)

    def _cancel_restore_metadata(self):
        for worker in tuple(self._metadata_workers):
            if worker.isRunning():
                worker.requestInterruption()
                worker.wait()
        worker = self._restore_metadata_worker
        if worker and worker.isRunning():
            worker.requestInterruption()
            worker.wait()

    def _add_list_item(self, track: Track):
        dur = format_duration(track.duration) if track.duration > 0 else "--:--"
        item = QListWidgetItem()
        item.setToolTip(track.path)
        item.setData(Qt.ItemDataRole.UserRole, track.path)
        item.setStatusTip(dur)
        self.list_widget.addItem(item)
        row = PlaylistTrackRow(
            track,
            self._normalized_path(track.path) in self._favorite_paths,
            self._theme_colors.get("accent", "#f5a623"),
            self.list_widget,
        )
        row.favorite_toggled.connect(self.favorite_toggled.emit)
        row.track_activated.connect(
            lambda item=item: self.track_activated.emit(self.list_widget.row(item))
        )
        item.setSizeHint(QSize(0, 36))
        self.list_widget.setItemWidget(item, row)

    @staticmethod
    def _normalized_path(path: str) -> str:
        return os.path.normcase(os.path.abspath(path))

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
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            row = self.list_widget.itemWidget(item)
            if isinstance(row, PlaylistTrackRow):
                row.set_active(i == index)
        if 0 <= index < self.list_widget.count():
            self.list_widget.scrollToItem(self.list_widget.item(index))

    def set_theme_colors(self, colors: dict):
        self._theme_colors = dict(colors)
        accent = colors.get("accent", "#f5a623")
        for button, icon_name in (
            (self.btn_add, "ajout.svg"),
            (self.btn_add_folder, "dossier.svg"),
            (self.btn_add_cd, "vinyle.svg"),
            (self.btn_remove, "retirer.svg"),
            (self.btn_clear, "corbeille.svg"),
        ):
            button.setIcon(self._tinted_icon(icon_name, accent))
        self.btn_open_playlist_manager.setIcon(
            self._tinted_icon("mesplaylists.svg", accent)
        )
        self.btn_play_favorites.setIcon(self._tinted_icon("heart.svg", accent))
        self.btn_play_favorites.setStyleSheet(f"QPushButton {{ color: {accent}; }}")
        for i in range(self.list_widget.count()):
            row = self.list_widget.itemWidget(self.list_widget.item(i))
            if isinstance(row, PlaylistTrackRow):
                row.set_theme_colors(colors)
        current_row = self.playlist.current_index
        self.set_active_row(current_row if 0 <= current_row < self.list_widget.count() else -1)

    @staticmethod
    def _tinted_icon(name: str, color: str) -> QIcon:
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

    def set_favorite_paths(self, paths):
        self._favorite_paths = {self._normalized_path(path) for path in paths}
        for i in range(self.list_widget.count()):
            row = self.list_widget.itemWidget(self.list_widget.item(i))
            if isinstance(row, PlaylistTrackRow):
                row.set_favorite(
                    self._normalized_path(row.track.path) in self._favorite_paths
                )

    def _update_count(self):
        n = len(self.playlist)
        dur = format_duration(self.playlist.total_duration)
        self.lbl_count.setText(f"{n} morceau{'x' if n > 1 else ''} · {dur}")
