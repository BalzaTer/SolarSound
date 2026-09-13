"""Panneau de gestion des playlists personnalisées (onglet "Mes Playlists")"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QFileDialog,
    QMessageBox, QFrame, QSizePolicy, QAbstractItemView, QInputDialog,
    QSplitter, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon, QAction, QKeySequence
import os
from datetime import datetime

try:
    from .playlist_dialogs import PlaylistDialog, PlaylistActionDialog, MOOD_ICONS
    from .progress_dialog import run_with_progress
    from ..core.playlist_manager import PlaylistManager
    from ..audio.metadata import format_duration, read_cover_art_data
except (ImportError, ModuleNotFoundError):
    from ui.playlist_dialogs import PlaylistDialog, PlaylistActionDialog, MOOD_ICONS
    from ui.progress_dialog import run_with_progress
    from core.playlist_manager import PlaylistManager
    from audio.metadata import format_duration, read_cover_art_data


ROLE = Qt.ItemDataRole.UserRole


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


class PlaylistTree(QTreeWidget):
    """
    Arbre des dossiers / playlists de l'onglet "Mes Playlists".

    - Glisser-déposer INTERNE : réordonner / déplacer une playlist dans un
      dossier (ou à la racine) -> signal `internal_order_changed`.
    - Glisser-déposer EXTERNE (dossiers venant de l'explorateur de fichiers,
      un ou plusieurs à la fois) -> signal `folders_dropped(paths, target_folder_id)`.
    """

    internal_order_changed = pyqtSignal()
    folders_dropped = pyqtSignal(list, object)  # (List[str], Optional[str])

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls() or event.source() is self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def _event_pos(self, event):
        # PyQt6 : QDropEvent.position() (QPointF) remplace pos() (déprécié)
        if hasattr(event, "position"):
            return event.position().toPoint()
        return event.pos()

    def _target_folder_id(self, event):
        item = self.itemAt(self._event_pos(event))
        if item is None:
            return None
        data = item.data(0, ROLE) or {}
        if data.get("type") == "folder":
            return data.get("id")
        if data.get("type") == "playlist":
            parent = item.parent()
            if parent is not None:
                pdata = parent.data(0, ROLE) or {}
                return pdata.get("id")
        return None

    def dropEvent(self, event):
        md = event.mimeData()
        if md.hasUrls() and event.source() is not self:
            folder_paths = [
                u.toLocalFile() for u in md.urls()
                if u.toLocalFile() and os.path.isdir(u.toLocalFile())
            ]
            if folder_paths:
                target_folder_id = self._target_folder_id(event)
                self.folders_dropped.emit(folder_paths, target_folder_id)
            event.acceptProposedAction()
            return

        super().dropEvent(event)
        self.internal_order_changed.emit()


class PlaylistManagerPanel(QWidget):
    """Gestionnaire de playlists personnalisées : dossiers + playlists + détails + CRUD"""

    # Émis quand l'utilisateur confirme le chargement d'une playlist perso
    # dans la liste de lecture principale : (playlist_id, action="replace"|"append")
    load_requested = pyqtSignal(str, str)

    def __init__(self, manager: PlaylistManager, get_library_folders=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._get_library_folders = get_library_folders or (lambda: [])
        self._current_playlist_id = None
        self._current_folder_id = None  # dossier sélectionné (item "dossier")
        self._setup_ui()
        self._connect_signals()
        self.refresh_playlists()

    # ── UI ──────────────────────────────────────────────────────────
    def _setup_ui(self):
        self._create_actions()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Colonne gauche : arbre dossiers / playlists ──────────────
        left_container = QWidget()
        left_col = QVBoxLayout(left_container)

        lbl_title = QLabel("Mes playlists")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        left_col.addWidget(lbl_title)

        hint = QLabel("Glissez un ou plusieurs dossiers ici pour créer une playlist par dossier")
        hint.setStyleSheet("font-size: 11px; color: #7a6a48;")
        hint.setWordWrap(True)
        left_col.addWidget(hint)

        self.tree_playlists = PlaylistTree()
        self.tree_playlists.setIconSize(QSize(48, 48))
        self.tree_playlists.setStyleSheet(
            "QTreeWidget { font-size: 13px; }"
            "QTreeWidget::item { padding: 6px 4px; }"
        )
        self.tree_playlists.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_playlists.addActions([
            self.act_new, self.act_new_folder, self.act_delete, self.act_duplicate,
            self.act_move_up, self.act_move_down, self.act_move_to_folder,
        ])
        left_col.addWidget(self.tree_playlists)

        left_buttons_row = QHBoxLayout()
        self.btn_new = QPushButton("＋ Nouvelle")
        self.btn_new.setToolTip("Nouvelle playlist (Ctrl+N)")
        self.btn_new_folder = QPushButton("📁 Nouveau dossier")
        self.btn_new_folder.setToolTip("Nouveau dossier (Ctrl+Maj+N)")
        left_buttons_row.addWidget(self.btn_new)
        left_buttons_row.addWidget(self.btn_new_folder)
        left_col.addLayout(left_buttons_row)

        library_buttons_row = QHBoxLayout()
        self.btn_backup_all = QPushButton("💾 Sauvegarder toutes les playlists")
        self.btn_backup_all.setToolTip("Enregistrer une copie du fichier JSON de toutes les playlists")
        library_buttons_row.addWidget(self.btn_backup_all)
        left_col.addLayout(library_buttons_row)

        scan_buttons_row = QHBoxLayout()
        self.btn_scan_library = QPushButton("🔍 Scanner les dossiers de musique")
        self.btn_scan_library.setToolTip(
            "Retrouver les pistes déplacées/renommées dans les dossiers de "
            "musique configurés (Paramètres → Bibliothèque)"
        )
        scan_buttons_row.addWidget(self.btn_scan_library)
        left_col.addLayout(scan_buttons_row)

        splitter.addWidget(left_container)

        # ── Colonne droite : détails + actions ──────────────────────
        right_container = QWidget()
        right_col = QVBoxLayout(right_container)

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

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 700])

        layout.addWidget(splitter)

        self._set_details_enabled(False)

    def _create_actions(self):
        """
        Actions pour les 7 opérations de l'arbre "Mes Playlists" — chacune
        porte son raccourci clavier et alimente aussi le menu contextuel
        (clic droit). Seules "Nouvelle" et "Nouveau dossier" ont un bouton
        visible ; les 5 autres ne sont accessibles qu'au clic droit ou au
        raccourci.
        """
        self.act_new = QAction("＋ Nouvelle playlist", self)
        self.act_new.setShortcut(QKeySequence("Ctrl+N"))
        self.act_new.triggered.connect(self._on_new)

        self.act_new_folder = QAction("📁 Nouveau dossier", self)
        self.act_new_folder.setShortcut(QKeySequence("Ctrl+Shift+N"))
        self.act_new_folder.triggered.connect(self._on_new_folder)

        self.act_delete = QAction("🗑 Supprimer", self)
        self.act_delete.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self.act_delete.triggered.connect(self._on_delete)

        self.act_duplicate = QAction("⧉ Dupliquer", self)
        self.act_duplicate.setShortcut(QKeySequence("Ctrl+D"))
        self.act_duplicate.triggered.connect(self._on_duplicate)

        self.act_move_up = QAction("▲ Monter", self)
        self.act_move_up.setShortcut(QKeySequence("Ctrl+Up"))
        self.act_move_up.triggered.connect(lambda: self._on_move_step("up"))

        self.act_move_down = QAction("▼ Descendre", self)
        self.act_move_down.setShortcut(QKeySequence("Ctrl+Down"))
        self.act_move_down.triggered.connect(lambda: self._on_move_step("down"))

        self.act_move_to_folder = QAction("→ 📁 Déplacer vers un dossier…", self)
        self.act_move_to_folder.setShortcut(QKeySequence("Ctrl+M"))
        self.act_move_to_folder.triggered.connect(self._on_move_to_folder)

        # Les raccourcis ne s'activent que quand l'arbre "Mes Playlists"
        # (ou l'un de ses enfants) a le focus, pour ne pas entrer en
        # conflit avec d'autres raccourcis ailleurs dans l'app (ex :
        # Suppr dans la liste des pistes à droite).
        for act in (
            self.act_new, self.act_new_folder, self.act_delete, self.act_duplicate,
            self.act_move_up, self.act_move_down, self.act_move_to_folder,
        ):
            act.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def _show_tree_context_menu(self, pos):
        item = self.tree_playlists.itemAt(pos)
        if item is not None:
            self.tree_playlists.setCurrentItem(item)

        has_playlist = self._get_current_playlist() is not None
        has_folder = self._get_current_folder() is not None
        has_selection = has_playlist or has_folder

        self.act_delete.setEnabled(has_selection)
        self.act_duplicate.setEnabled(has_playlist)
        self.act_move_up.setEnabled(has_selection)
        self.act_move_down.setEnabled(has_selection)
        self.act_move_to_folder.setEnabled(has_playlist)

        menu = QMenu(self)
        menu.addAction(self.act_new)
        menu.addAction(self.act_new_folder)
        menu.addSeparator()
        menu.addAction(self.act_delete)
        menu.addAction(self.act_duplicate)
        menu.addAction(self.act_move_up)
        menu.addAction(self.act_move_down)
        menu.addAction(self.act_move_to_folder)
        menu.exec(self.tree_playlists.viewport().mapToGlobal(pos))

    def _connect_signals(self):
        self.tree_playlists.currentItemChanged.connect(self._on_selection_changed)
        self.tree_playlists.internal_order_changed.connect(self._on_tree_internal_change)
        self.tree_playlists.folders_dropped.connect(self._on_folders_dropped)
        self.tree_playlists.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.tree_playlists.itemExpanded.connect(lambda item: self._on_folder_expansion_changed(item, True))
        self.tree_playlists.itemCollapsed.connect(lambda item: self._on_folder_expansion_changed(item, False))

        self.btn_new.clicked.connect(self._on_new)
        self.btn_new_folder.clicked.connect(self._on_new_folder)
        self.btn_backup_all.clicked.connect(self._on_backup_all)
        self.btn_scan_library.clicked.connect(self._on_scan_library)

        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_add_files.clicked.connect(self._on_add_files)
        self.btn_add_folder.clicked.connect(self._on_add_folder)
        self.btn_load.clicked.connect(self._on_load)
        self.btn_remove_track.clicked.connect(self._on_remove_track)
        self.list_tracks.order_changed.connect(self._on_tracks_reordered)

    def _set_details_enabled(self, enabled: bool):
        for w in (self.btn_edit, self.btn_add_files, self.btn_add_folder, self.btn_load):
            w.setEnabled(enabled)

    # ── Rafraîchissement de l'arbre ────────────────────────────────
    def refresh_playlists(self):
        """Recharge l'arbre dossiers/playlists depuis le manager"""
        previous_playlist_id = self._current_playlist_id
        previous_folder_id = self._current_folder_id

        self.tree_playlists.blockSignals(True)
        self.tree_playlists.clear()

        folders = sorted(self.manager.get_all_folders(), key=lambda f: f.order)
        playlists = self.manager.get_all_playlists()

        by_folder = {}
        root_playlists = []
        for p in playlists:
            if p.folder_id:
                by_folder.setdefault(p.folder_id, []).append(p)
            else:
                root_playlists.append(p)
        root_playlists.sort(key=lambda p: p.order)

        restore_item = None

        for folder in folders:
            folder_item = QTreeWidgetItem([f"📁 {folder.name}"])
            folder_item.setData(0, ROLE, {"type": "folder", "id": folder.id})
            folder_item.setFlags(
                folder_item.flags() | Qt.ItemFlag.ItemIsDropEnabled
            )
            font = folder_item.font(0)
            font.setBold(True)
            folder_item.setFont(0, font)
            self.tree_playlists.addTopLevelItem(folder_item)
            if folder.id == previous_folder_id:
                restore_item = folder_item

            children = sorted(by_folder.get(folder.id, []), key=lambda p: p.order)
            for playlist in children:
                item = self._make_playlist_item(playlist)
                folder_item.addChild(item)
                if playlist.id == previous_playlist_id:
                    restore_item = item
            folder_item.setExpanded(folder.expanded)

        for playlist in root_playlists:
            item = self._make_playlist_item(playlist)
            self.tree_playlists.addTopLevelItem(item)
            if playlist.id == previous_playlist_id:
                restore_item = item

        self.tree_playlists.blockSignals(False)

        if restore_item is not None:
            self.tree_playlists.setCurrentItem(restore_item)
            self._on_selection_changed(restore_item, None)
        else:
            first_item = self.tree_playlists.topLevelItem(0)
            if first_item is not None:
                self.tree_playlists.setCurrentItem(first_item)
                self._on_selection_changed(first_item, None)
            else:
                self._current_playlist_id = None
                self._current_folder_id = None
                self._refresh_details(None)

    def _make_playlist_item(self, playlist):
        item = QTreeWidgetItem([playlist.name or "(Sans nom)"])
        item.setData(0, ROLE, {"type": "playlist", "id": playlist.id})
        # Une playlist n'accepte pas d'enfant (pas de sous-playlist)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
        icon = self._cover_icon(playlist)
        if icon:
            item.setIcon(0, icon)
        return item

    def _cover_icon(self, playlist):
        """
        Retourne une icône de cover pour la playlist :
        - la cover dédiée si elle existe,
        - sinon la première pochette embarquée trouvée parmi ses pistes
          (pas forcément celle de la première piste).
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

    # ── Sélection ──────────────────────────────────────────────────
    def _on_folder_expansion_changed(self, item, expanded: bool):
        """Mémorise le pli/dépli manuel d'un dossier (ignoré pendant refresh_playlists,
        qui bloque les signaux du QTreeWidget le temps de reconstruire l'arbre)."""
        data = item.data(0, ROLE) or {}
        if data.get("type") == "folder":
            self.manager.set_folder_expanded(data["id"], expanded)

    def _on_selection_changed(self, current, previous):
        data = current.data(0, ROLE) if current else None
        data = data or {}

        if data.get("type") == "playlist":
            self._current_playlist_id = data.get("id")
            self._current_folder_id = None
            playlist = self.manager.get_playlist(self._current_playlist_id)
            self._refresh_details(playlist)
        elif data.get("type") == "folder":
            self._current_playlist_id = None
            self._current_folder_id = data.get("id")
            self._refresh_details(None)
        else:
            self._current_playlist_id = None
            self._current_folder_id = None
            self._refresh_details(None)

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
            item.setData(ROLE, i)
            self.list_tracks.addItem(item)

    # ── Actions CRUD playlists ──────────────────────────────────────
    def _current_scope_folder_id(self):
        """Dossier dans lequel une nouvelle playlist doit être créée (None = racine)"""
        if self._current_folder_id:
            return self._current_folder_id
        if self._current_playlist_id:
            playlist = self.manager.get_playlist(self._current_playlist_id)
            if playlist:
                return playlist.folder_id
        return None

    def _on_new(self):
        dialog = PlaylistDialog(parent=self)
        if dialog.exec():
            data = dialog.result_data()
            if not data["name"]:
                return
            playlist = self.manager.create_playlist(
                data["name"], data["moods"], folder_id=self._current_scope_folder_id()
            )
            if data["cover_source_path"]:
                self._apply_cover(playlist.id, data["cover_source_path"])
            self.refresh_playlists()
            self._select_playlist_id(playlist.id)

    def _on_new_folder(self):
        name, ok = QInputDialog.getText(self, "Nouveau dossier", "Nom du dossier :")
        if ok and name.strip():
            folder = self.manager.create_folder(name.strip())
            self.refresh_playlists()
            self._select_folder_id(folder.id)

    def _on_backup_all(self):
        default_name = f"solarsound_playlists_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder toutes les playlists", default_name, "Fichiers JSON (*.json)"
        )
        if not path:
            return
        if self.manager.backup_to(path):
            QMessageBox.information(self, "Sauvegarde", f"Playlists sauvegardées dans :\n{path}")
        else:
            QMessageBox.warning(self, "Sauvegarde", "Impossible de créer la sauvegarde.")

    def _on_scan_library(self):
        folders = [f for f in (self._get_library_folders() or []) if f]
        if not folders:
            QMessageBox.information(
                self, "Scanner les dossiers de musique",
                "Aucun dossier de musique n'est configuré.\n"
                "Ajoutez-en dans Paramètres → Bibliothèque."
            )
            return

        run_with_progress(
            self, "Recherche des pistes manquantes",
            "Analyse des dossiers de musique…",
            self.manager.relocate_missing_tracks,
            on_success=self._on_scan_library_result,
            on_error=self._on_scan_library_error,
            library_folders=folders,
        )

    def _on_scan_library_result(self, result: dict):
        self.refresh_playlists()

        if result["missing"] == 0:
            QMessageBox.information(
                self, "Scanner les dossiers de musique",
                "Toutes les pistes de vos playlists sont bien présentes, rien à corriger."
            )
            return

        details = ""
        if result["still_missing"]:
            lines = "\n".join(f"• {name} — {title}" for name, title in result["still_missing"][:15])
            remaining = len(result["still_missing"]) - 15
            more = f"\n… et {remaining} autre(s)" if remaining > 0 else ""
            details = f"\n\nToujours introuvables :\n{lines}{more}"

        QMessageBox.information(
            self, "Scanner les dossiers de musique",
            f"{result['relocated']} piste(s) sur {result['missing']} manquante(s) ont été "
            f"retrouvées et corrigées.{details}"
        )

    def _on_scan_library_error(self, message: str):
        QMessageBox.warning(
            self, "Scanner les dossiers de musique",
            f"La recherche a échoué :\n{message}"
        )

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
        elif self.manager.cover_handler.pil_available is False:
            QMessageBox.warning(
                self, "Cover non enregistrée",
                "Impossible d'enregistrer l'image : le module Pillow n'est pas installé.\n\n"
                "Installez-le avec : pip install Pillow\n"
                "puis réessayez."
            )
        else:
            QMessageBox.warning(
                self, "Cover non enregistrée",
                "L'image sélectionnée n'a pas pu être enregistrée (fichier invalide ou illisible)."
            )

    def _on_delete(self):
        playlist = self._get_current_playlist()
        if playlist:
            reply = QMessageBox.question(
                self, "Supprimer la playlist",
                f'Voulez-vous vraiment supprimer "{playlist.name}" ?\n'
                "Les fichiers audio ne seront pas supprimés, seule la playlist le sera.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.manager.delete_playlist(playlist.id)
                self.refresh_playlists()
            return

        folder = self._get_current_folder()
        if folder:
            reply = QMessageBox.question(
                self, "Supprimer le dossier",
                f'Voulez-vous vraiment supprimer le dossier "{folder.name}" ?\n'
                "Les playlists qu'il contient seront remontées à la racine (elles ne "
                "seront pas supprimées).",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.manager.delete_folder(folder.id)
                self.refresh_playlists()

    def _on_duplicate(self):
        playlist = self._get_current_playlist()
        if not playlist:
            return
        new_playlist = self.manager.duplicate_playlist(playlist.id)
        if new_playlist:
            self.refresh_playlists()
            self._select_playlist_id(new_playlist.id)

    def _on_move_step(self, direction: str):
        playlist = self._get_current_playlist()
        if playlist:
            if self.manager.move_playlist_step(playlist.id, direction):
                self.refresh_playlists()
                self._select_playlist_id(playlist.id)
            return

        folder = self._get_current_folder()
        if folder:
            if self.manager.move_folder_step(folder.id, direction):
                self.refresh_playlists()
                self._select_folder_id(folder.id)

    def _on_move_to_folder(self):
        playlist = self._get_current_playlist()
        if not playlist:
            return
        folders = self.manager.get_all_folders()
        options = ["(Racine)"] + [f.name for f in folders]
        current_label = "(Racine)"
        if playlist.folder_id:
            current_folder = self.manager.get_folder(playlist.folder_id)
            if current_folder:
                current_label = current_folder.name
        choice, ok = QInputDialog.getItem(
            self, "Déplacer la playlist", "Vers :", options,
            options.index(current_label) if current_label in options else 0, False,
        )
        if not ok:
            return
        target_folder_id = None
        if choice != "(Racine)":
            for f in folders:
                if f.name == choice:
                    target_folder_id = f.id
                    break
        self.manager.move_playlist_to_folder(playlist.id, target_folder_id)
        self.refresh_playlists()
        self._select_playlist_id(playlist.id)

    # ── Ajout de contenu à une playlist ──────────────────────────────
    def _on_add_files(self):
        playlist = self._get_current_playlist()
        if not playlist:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Ajouter des fichiers à la playlist",
            "", "Fichiers média (*.mp3 *.wav *.flac *.ogg *.opus *.aiff *.aif *.au *.mp4 *.mkv *.avi *.mov *.wmv *.m4v *.flv *.webm);;Tous (*.*)"
        )
        if not paths:
            return
        run_with_progress(
            self, "Ajout de fichiers", "Ajout des pistes à la playlist…",
            self.manager.add_tracks_to_playlist,
            on_success=lambda _n: self._refresh_details(self.manager.get_playlist(playlist.id)),
            on_error=self._on_library_task_error,
            playlist_id=playlist.id, file_paths=paths,
        )

    def _on_add_folder(self):
        playlist = self._get_current_playlist()
        if not playlist:
            return
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if not folder:
            return
        run_with_progress(
            self, "Ajout d'un dossier", "Recherche des fichiers…",
            self.manager.add_folder_to_playlist,
            on_success=lambda _n: self._refresh_details(self.manager.get_playlist(playlist.id)),
            on_error=self._on_library_task_error,
            playlist_id=playlist.id, folder_path=folder,
        )

    def _on_library_task_error(self, message: str):
        QMessageBox.warning(self, "Erreur", f"L'opération a échoué :\n{message}")

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
        index = item.data(ROLE)
        self.manager.remove_track_from_playlist(playlist.id, index)
        self._refresh_details(self.manager.get_playlist(playlist.id))

    def _on_tracks_reordered(self):
        """Persiste le nouvel ordre après un glisser-déposer dans la liste des pistes."""
        playlist = self._get_current_playlist()
        if not playlist:
            return
        new_order = [
            self.list_tracks.item(i).data(ROLE)
            for i in range(self.list_tracks.count())
        ]
        self.manager.reorder_playlist_tracks(playlist.id, new_order)
        # Resynchronise les index UserRole avec le nouvel ordre enregistré
        self._refresh_details(self.manager.get_playlist(playlist.id))

    # ── Glisser-déposer de dossiers OS (création multi-playlists) ────
    def _on_folders_dropped(self, folder_paths, target_folder_id):
        run_with_progress(
            self, "Création de playlists", "Analyse des dossiers déposés…",
            self.manager.create_playlists_from_folders,
            on_success=self._on_folders_dropped_result,
            on_error=self._on_library_task_error,
            folder_paths=folder_paths, target_folder_id=target_folder_id,
        )

    def _on_folders_dropped_result(self, created):
        self.refresh_playlists()
        if created:
            names = ", ".join(f'"{p.name}"' for p in created)
            self._select_playlist_id(created[-1].id)
            QMessageBox.information(
                self, "Playlists créées",
                f"{len(created)} playlist(s) créée(s) : {names}"
            )
        else:
            QMessageBox.information(
                self, "Aucune playlist créée",
                "Aucun fichier audio n'a été trouvé dans le(s) dossier(s) déposé(s)."
            )

    # ── Glisser-déposer interne (réordonner / déplacer dans l'arbre) ─
    def _on_tree_internal_change(self):
        """Persiste la structure (dossiers + playlists) après un glisser-déposer dans l'arbre."""
        root_order = 0
        folder_order = 0
        for i in range(self.tree_playlists.topLevelItemCount()):
            top_item = self.tree_playlists.topLevelItem(i)
            data = top_item.data(0, ROLE) or {}

            if data.get("type") == "folder":
                self.manager.set_folder_position(data["id"], folder_order)
                folder_order += 1
                child_order = 0
                for j in range(top_item.childCount()):
                    child = top_item.child(j)
                    cdata = child.data(0, ROLE) or {}
                    if cdata.get("type") == "playlist":
                        self.manager.set_playlist_position(cdata["id"], data["id"], child_order)
                        child_order += 1

            elif data.get("type") == "playlist":
                self.manager.set_playlist_position(data["id"], None, root_order)
                root_order += 1

        self.manager.save_all()
        self.refresh_playlists()

    # ── Helpers ───────────────────────────────────────────────────────
    def _get_current_playlist(self):
        if not self._current_playlist_id:
            return None
        return self.manager.get_playlist(self._current_playlist_id)

    def _get_current_folder(self):
        if not self._current_folder_id:
            return None
        return self.manager.get_folder(self._current_folder_id)

    def _select_playlist_id(self, playlist_id: str):
        self._walk_and_select(lambda d: d.get("type") == "playlist" and d.get("id") == playlist_id)

    def _select_folder_id(self, folder_id: str):
        self._walk_and_select(lambda d: d.get("type") == "folder" and d.get("id") == folder_id)

    def _walk_and_select(self, predicate):
        for i in range(self.tree_playlists.topLevelItemCount()):
            top_item = self.tree_playlists.topLevelItem(i)
            if predicate(top_item.data(0, ROLE) or {}):
                self.tree_playlists.setCurrentItem(top_item)
                return
            for j in range(top_item.childCount()):
                child = top_item.child(j)
                if predicate(child.data(0, ROLE) or {}):
                    self.tree_playlists.setCurrentItem(child)
                    return

    def set_theme_colors(self, colors: dict):
        """Réservé pour une future intégration du theming (appelé par MainWindow)"""
        pass
