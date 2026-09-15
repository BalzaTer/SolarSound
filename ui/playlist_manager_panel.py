"""Panneau de gestion des playlists personnalisées (onglet "Mes Playlists")"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QFileDialog,
    QMessageBox, QFrame, QSizePolicy, QAbstractItemView, QInputDialog,
    QSplitter, QMenu, QStackedWidget, QButtonGroup, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon, QAction, QKeySequence, QPainter
from PyQt6.QtSvg import QSvgRenderer
import os
from datetime import datetime

try:
    from .playlist_dialogs import PlaylistDialog, PlaylistActionDialog, MOOD_ICONS
    from .progress_dialog import run_with_progress
    from ..core.playlist_manager import PlaylistManager
    from ..audio.metadata import format_duration, read_cover_art_data
    from ..core.i18n import tr
except (ImportError, ModuleNotFoundError):
    from ui.playlist_dialogs import PlaylistDialog, PlaylistActionDialog, MOOD_ICONS
    from ui.progress_dialog import run_with_progress
    from core.playlist_manager import PlaylistManager
    from audio.metadata import format_duration, read_cover_art_data
    from core.i18n import tr


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


class PlaylistBrowserView(QWidget):
    """
    Vue "à plat" d'un seul niveau de dossier, façon explorateur Windows
    (mode "Détails" ou "Icônes") : une barre de chemin en haut, double-clic
    pour entrer dans un dossier, simple clic pour sélectionner une
    playlist ou un dossier.

    Comme les dossiers de "Mes Playlists" ne peuvent pas être imbriqués
    (un dossier ne contient que des playlists), il n'y a qu'un seul
    niveau à parcourir : la racine, ou l'intérieur d'un dossier.
    """

    selection_changed = pyqtSignal(object)      # dict {"type","id"} ou None
    navigation_changed = pyqtSignal(object)      # id du dossier affiché (None = racine)
    context_menu_requested = pyqtSignal(object)  # QPoint global, prêt pour menu.exec()

    def __init__(self, manager: PlaylistManager, mode: str, get_cover_icon, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.mode = mode  # "details" ou "icons"
        self._get_cover_icon = get_cover_icon
        self._folder_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        path_row = QHBoxLayout()
        self.btn_up = QPushButton("⬆")
        self.btn_up.setFixedWidth(28)
        self.btn_up.setToolTip(tr("playlists.up_tooltip"))
        self.btn_up.setEnabled(False)
        self.btn_up.clicked.connect(lambda: self.navigate_to(None))
        path_row.addWidget(self.btn_up)

        self.lbl_path = QLabel(tr("playlists.root"))
        self.lbl_path.setStyleSheet("font-weight: bold;")
        path_row.addWidget(self.lbl_path)
        path_row.addStretch()
        layout.addLayout(path_row)

        folder_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        self._folder_icon = folder_icon

        if self.mode == "details":
            self.view = QTreeWidget()
            self.view.setColumnCount(3)
            self.view.setHeaderLabels([tr("playlists.col.name"), tr("playlists.col.type"), tr("playlists.col.tracks")])
            self.view.setRootIsDecorated(False)
            self.view.setUniformRowHeights(True)
            self.view.setIconSize(QSize(24, 24))
        else:
            self.view = QListWidget()
            self.view.setViewMode(QListWidget.ViewMode.IconMode)
            self.view.setIconSize(QSize(72, 72))
            self.view.setGridSize(QSize(120, 110))
            self.view.setResizeMode(QListWidget.ResizeMode.Adjust)
            self.view.setMovement(QListWidget.Movement.Static)
            self.view.setWordWrap(True)

        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.itemSelectionChanged.connect(self._on_selection_changed)
        self.view.itemDoubleClicked.connect(self._on_item_activated)
        self.view.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.view)

    def retranslate(self):
        """En-têtes et infobulle : posés une seule fois dans _build_ui,
        donc à remettre explicitement après un changement de langue."""
        self.btn_up.setToolTip(tr("playlists.up_tooltip"))
        if self.mode == "details":
            self.view.setHeaderLabels([
                tr("playlists.col.name"), tr("playlists.col.type"), tr("playlists.col.tracks")
            ])
        self.refresh()

    # ── Navigation ───────────────────────────────────────────────────
    def navigate_to(self, folder_id):
        if folder_id is not None and not self.manager.get_folder(folder_id):
            folder_id = None
        self._folder_id = folder_id
        self.refresh()
        self.navigation_changed.emit(folder_id)
        self._on_selection_changed()

    def current_folder_id(self):
        return self._folder_id

    def set_current_folder_silent(self, folder_id):
        """Change le dossier courant sans reconstruire ni émettre de signal (sync interne)."""
        self._folder_id = folder_id

    # ── Rafraîchissement ────────────────────────────────────────────
    def refresh(self):
        if self._folder_id is not None and not self.manager.get_folder(self._folder_id):
            self._folder_id = None  # le dossier parcouru a été supprimé entre-temps

        if self._folder_id is None:
            self.lbl_path.setText(tr("playlists.root"))
            self.btn_up.setEnabled(False)
        else:
            folder = self.manager.get_folder(self._folder_id)
            self.lbl_path.setText(f'{tr("playlists.root")} ▸ 📁 {folder.name}')
            self.btn_up.setEnabled(True)

        if self.mode == "details":
            self._rebuild_details()
        else:
            self._rebuild_icons()

    def _current_entries(self):
        """Liste (type, objet) des entrées à afficher dans le dossier courant."""
        entries = []
        if self._folder_id is None:
            folders = sorted(self.manager.get_all_folders(), key=lambda f: f.order)
            entries.extend(("folder", f) for f in folders)
            playlists = [p for p in self.manager.get_all_playlists() if not p.folder_id]
        else:
            playlists = [p for p in self.manager.get_all_playlists() if p.folder_id == self._folder_id]
        entries.extend(("playlist", p) for p in sorted(playlists, key=lambda p: p.order))
        return entries

    def _rebuild_details(self):
        self.view.blockSignals(True)
        self.view.clear()
        for entry_type, obj in self._current_entries():
            if entry_type == "folder":
                item = QTreeWidgetItem([f"{obj.name}", tr("playlists.type.folder"), ""])
                item.setIcon(0, self._folder_icon)
                item.setData(0, ROLE, {"type": "folder", "id": obj.id})
            else:
                item = QTreeWidgetItem([obj.name or tr("playlists.unnamed"), tr("playlists.type.playlist"), str(len(obj.tracks))])
                item.setData(0, ROLE, {"type": "playlist", "id": obj.id})
                icon = self._get_cover_icon(obj)
                if icon:
                    item.setIcon(0, icon)
            self.view.addTopLevelItem(item)
        for col in range(self.view.columnCount()):
            self.view.resizeColumnToContents(col)
        self.view.blockSignals(False)

    def _rebuild_icons(self):
        self.view.blockSignals(True)
        self.view.clear()
        for entry_type, obj in self._current_entries():
            if entry_type == "folder":
                item = QListWidgetItem(self._folder_icon, obj.name)
                item.setData(ROLE, {"type": "folder", "id": obj.id})
            else:
                icon = self._get_cover_icon(obj) or QIcon()
                item = QListWidgetItem(icon, obj.name or tr("playlists.unnamed"))
                item.setData(ROLE, {"type": "playlist", "id": obj.id})
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.view.addItem(item)
        self.view.blockSignals(False)

    # ── Sélection / activation ───────────────────────────────────────
    def _item_data(self, item):
        if item is None:
            return None
        return (item.data(0, ROLE) if self.mode == "details" else item.data(ROLE)) or None

    def _on_selection_changed(self):
        self.selection_changed.emit(self._item_data(self.view.currentItem()))

    def _on_item_activated(self, item):
        data = self._item_data(item)
        if data and data.get("type") == "folder":
            self.navigate_to(data.get("id"))

    def _on_context_menu(self, pos):
        item = self.view.itemAt(pos)
        if item is not None:
            self.view.setCurrentItem(item)
        self.context_menu_requested.emit(self.view.viewport().mapToGlobal(pos))

    def select_id(self, entry_type: str, entry_id: str):
        count = self.view.topLevelItemCount() if self.mode == "details" else self.view.count()
        for i in range(count):
            item = self.view.topLevelItem(i) if self.mode == "details" else self.view.item(i)
            data = self._item_data(item) or {}
            if data.get("type") == entry_type and data.get("id") == entry_id:
                self.view.setCurrentItem(item)
                return
        # Rien à sélectionner (élément introuvable dans ce dossier) : vider la sélection.
        self.view.setCurrentItem(None)


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
        self._view_mode = "tree"        # "tree" | "details" | "icons"
        self._browse_folder_id = None   # dossier parcouru dans les vues "à plat"
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

        # ── Sélecteur de mode d'affichage (Arbre / Détails / Icônes) ─
        view_mode_row = QHBoxLayout()
        self.btn_view_tree = QPushButton(tr("playlists.view.tree"))
        self.btn_view_details = QPushButton(tr("playlists.view.details"))
        self.btn_view_icons = QPushButton(tr("playlists.view.icons"))
        for btn in (self.btn_view_tree, self.btn_view_details, self.btn_view_icons):
            btn.setCheckable(True)
            view_mode_row.addWidget(btn)
        self.btn_view_tree.setChecked(True)
        self._view_mode_group = QButtonGroup(self)
        self._view_mode_group.setExclusive(True)
        for btn in (self.btn_view_tree, self.btn_view_details, self.btn_view_icons):
            self._view_mode_group.addButton(btn)
        left_col.addLayout(view_mode_row)

        self.tree_playlists = PlaylistTree()
        self.tree_playlists.setIconSize(QSize(48, 48))
        self.tree_playlists.setStyleSheet(
            "QTreeWidget { font-size: 13px; }"
            "QTreeWidget::item { padding: 6px 4px; }"
        )
        self.tree_playlists.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.view_details = PlaylistBrowserView(self.manager, "details", self._cover_icon, self)
        self.view_icons = PlaylistBrowserView(self.manager, "icons", self._cover_icon, self)

        for view in (self.tree_playlists, self.view_details.view, self.view_icons.view):
            view.addActions([
                self.act_new, self.act_new_folder, self.act_delete, self.act_duplicate,
                self.act_move_up, self.act_move_down, self.act_move_to_folder,
            ])

        self.stack_views = QStackedWidget()
        self.stack_views.addWidget(self.tree_playlists)
        self.stack_views.addWidget(self.view_details)
        self.stack_views.addWidget(self.view_icons)
        left_col.addWidget(self.stack_views)

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
        self.lbl_cover.setPixmap(self._default_cover_pixmap(QSize(80, 80)))
        self.lbl_cover.setText("")
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

    def _build_context_menu(self) -> QMenu:
        """Construit le menu contextuel (partagé par les 3 vues) en fonction
        de la sélection courante (`_current_playlist_id` / `_current_folder_id`)."""
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
        return menu

    def _show_tree_context_menu(self, pos):
        item = self.tree_playlists.itemAt(pos)
        if item is not None:
            self.tree_playlists.setCurrentItem(item)
        self._build_context_menu().exec(self.tree_playlists.viewport().mapToGlobal(pos))

    def _show_flat_context_menu(self, global_pos):
        self._build_context_menu().exec(global_pos)

    def _connect_signals(self):
        self.tree_playlists.currentItemChanged.connect(self._on_selection_changed)
        self.tree_playlists.internal_order_changed.connect(self._on_tree_internal_change)
        self.tree_playlists.folders_dropped.connect(self._on_folders_dropped)
        self.tree_playlists.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.tree_playlists.itemExpanded.connect(lambda item: self._on_folder_expansion_changed(item, True))
        self.tree_playlists.itemCollapsed.connect(lambda item: self._on_folder_expansion_changed(item, False))

        for view in (self.view_details, self.view_icons):
            view.selection_changed.connect(self._apply_selection)
            view.navigation_changed.connect(self._on_flat_navigation_changed)
            view.context_menu_requested.connect(self._show_flat_context_menu)

        self.btn_view_tree.clicked.connect(lambda: self._on_view_mode_changed("tree"))
        self.btn_view_details.clicked.connect(lambda: self._on_view_mode_changed("details"))
        self.btn_view_icons.clicked.connect(lambda: self._on_view_mode_changed("icons"))

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

    def retranslate_ui(self):
        """Textes de ce panneau à remettre à jour après un changement de langue."""
        self.btn_view_tree.setText(tr("playlists.view.tree"))
        self.btn_view_details.setText(tr("playlists.view.details"))
        self.btn_view_icons.setText(tr("playlists.view.icons"))
        for view in (self.view_details, self.view_icons):
            view.retranslate()

    # ── Mode d'affichage (Arbre / Détails / Icônes) ─────────────────
    def get_view_mode(self) -> str:
        return self._view_mode

    def set_view_mode(self, mode: str):
        """Applique un mode d'affichage (utilisé aussi à la restauration de session)."""
        if mode not in ("tree", "details", "icons"):
            mode = "tree"
        btn = {
            "tree": self.btn_view_tree,
            "details": self.btn_view_details,
            "icons": self.btn_view_icons,
        }[mode]
        btn.setChecked(True)
        self._on_view_mode_changed(mode)

    def _on_view_mode_changed(self, mode: str):
        self._view_mode = mode

        if mode == "tree":
            self.stack_views.setCurrentWidget(self.tree_playlists)
            return

        view = self.view_details if mode == "details" else self.view_icons

        # Retrouver où se trouve la sélection courante pour que la vue "à
        # plat" affiche le bon dossier au moment du changement de mode.
        if self._current_playlist_id:
            playlist = self.manager.get_playlist(self._current_playlist_id)
            target_folder = playlist.folder_id if playlist else self._browse_folder_id
        elif self._current_folder_id:
            target_folder = None  # un dossier sélectionné est listé à la racine
        else:
            target_folder = self._browse_folder_id

        if view.current_folder_id() != target_folder:
            view.navigate_to(target_folder)
        self._browse_folder_id = target_folder

        if self._current_playlist_id:
            view.select_id("playlist", self._current_playlist_id)
        elif self._current_folder_id:
            view.select_id("folder", self._current_folder_id)

        self.stack_views.setCurrentWidget(view)

    def _on_flat_navigation_changed(self, folder_id):
        """Garde les 2 vues "à plat" synchronisées sur le même dossier parcouru,
        pour ne pas revenir à la racine en changeant simplement de mode d'affichage."""
        self._browse_folder_id = folder_id
        other = self.view_icons if self.sender() is self.view_details else self.view_details
        if other.current_folder_id() != folder_id:
            other.navigate_to(folder_id)

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

        # Garder les vues "à plat" synchronisées avec les données, en
        # conservant leur dossier parcouru.
        self.view_details.refresh()
        self.view_icons.refresh()
        if self._view_mode != "tree":
            if self._current_playlist_id and self.manager.get_playlist(self._current_playlist_id):
                self._select_playlist_id(self._current_playlist_id)
            elif self._current_folder_id and self.manager.get_folder(self._current_folder_id):
                self._select_folder_id(self._current_folder_id)

    def _make_playlist_item(self, playlist):
        item = QTreeWidgetItem([playlist.name or "(Sans nom)"])
        item.setData(0, ROLE, {"type": "playlist", "id": playlist.id})
        # Une playlist n'accepte pas d'enfant (pas de sous-playlist)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
        icon = self._cover_icon(playlist)
        if icon:
            item.setIcon(0, icon)
        return item

    @staticmethod
    def _default_cover_pixmap(size):
        """Retourne la couverture par défaut au format SVG."""
        default_cover_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "icons",
            "defaultcover.svg",
        )
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(default_cover_path)
        if not renderer.isValid():
            return pixmap
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return pixmap

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

        return QIcon(self._default_cover_pixmap(QSize(80, 80)))

    # ── Sélection ──────────────────────────────────────────────────
    def _on_folder_expansion_changed(self, item, expanded: bool):
        """Mémorise le pli/dépli manuel d'un dossier (ignoré pendant refresh_playlists,
        qui bloque les signaux du QTreeWidget le temps de reconstruire l'arbre)."""
        data = item.data(0, ROLE) or {}
        if data.get("type") == "folder":
            self.manager.set_folder_expanded(data["id"], expanded)

    def _on_selection_changed(self, current, previous):
        self._apply_selection(current.data(0, ROLE) if current else None)

    def _apply_selection(self, data):
        """Point d'entrée unique de la sélection, quelle que soit la vue active
        (arbre, détails ou icônes)."""
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
            self.lbl_cover.setPixmap(self._default_cover_pixmap(QSize(80, 80)))
            self.lbl_cover.setText("")
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
            self.lbl_cover.setPixmap(self._default_cover_pixmap(QSize(80, 80)))
            self.lbl_cover.setText("")

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
        if self._view_mode != "tree":
            return self._browse_folder_id
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
        if self._view_mode == "tree":
            self._walk_and_select(lambda d: d.get("type") == "playlist" and d.get("id") == playlist_id)
            return
        playlist = self.manager.get_playlist(playlist_id)
        if not playlist:
            return
        view = self.view_details if self._view_mode == "details" else self.view_icons
        if view.current_folder_id() != playlist.folder_id:
            view.navigate_to(playlist.folder_id)
        self._browse_folder_id = playlist.folder_id
        view.select_id("playlist", playlist_id)

    def _select_folder_id(self, folder_id: str):
        if self._view_mode == "tree":
            self._walk_and_select(lambda d: d.get("type") == "folder" and d.get("id") == folder_id)
            return
        view = self.view_details if self._view_mode == "details" else self.view_icons
        if view.current_folder_id() is not None:
            view.navigate_to(None)
        self._browse_folder_id = None
        view.select_id("folder", folder_id)

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
