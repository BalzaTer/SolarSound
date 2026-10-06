"""Fenêtre principale SolarSound"""

import os
import time
import sys
import random
from typing import List

from PyQt6.QtWidgets import (
    QTabBar,
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget,
    QPushButton, QLabel, QSlider, QTabWidget, QFrame,
    QSizePolicy, QMenuBar, QStatusBar, QMessageBox,
    QFileDialog, QGroupBox, QApplication,
    QLineEdit, QListWidget, QListWidgetItem, QStyledItemDelegate
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize, pyqtSignal, QPoint, QEvent, QRect
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPixmap, QPainter, QCursor
from PyQt6.QtSvg import QSvgRenderer

try:
    from .settings_panel import SettingsPanel, build_stylesheet, DEFAULT_SHORTCUTS, DEFAULT_COLORS, DEFAULT_FONT
    from .video_window import VideoWindow
    from ..video.player import VideoEngine, SUPPORTED_VIDEO_FORMATS
    from .theme import STYLESHEET
    from .playlist_widget import FavoriteButton, PlaylistWidget
    from .playlist_manager_panel import PlaylistManagerPanel
    from .spatial_panel import SpatialPanel
    from .rotation_panel import RotationPanel
    from .vinyl_panel import VinylPanel
    from .equalizer_panel import EqualizerPanel
    from .visualizer_widget import SolarVisualizer, N_BANDS as VIZ_N_BANDS
    from .progress_widget import ClickableProgressSlider, IntensityProgressBar
    from ..core.playlist import Playlist, PlayMode, Track
    from ..core.session import SessionManager, SessionState, WindowState
    from ..core.playlist_manager import PlaylistManager
    from ..core.custom_playlist import CustomTrack, MoodEnum
    from ..core.startup import set_launch_at_startup
    from ..audio.engine import AudioEngine, SpatialConfig
    from ..audio.cd import parse_cd_uri
    from ..audio.cd_metadata import get_cached_cover_for_drive
    from ..core.library_scanner import scan_library_folders
    from .progress_dialog import TaskWorker
    from ..audio.preview_player import PreviewPlayer
    from ..audio.metadata import format_duration, read_metadata, read_cover_art_data
    from ..core.error_logging import append_error_log
    from ..core.volume import SLIDER_MAX, gain_to_slider_value, slider_to_gain
    from ..core.i18n import tr, set_language, get_language, DEFAULT_LANGUAGE
except (ImportError, ModuleNotFoundError):
    # If this module is run directly (python ui/main_window.py), absolute
    # imports like "ui.settings_panel" may fail because the package root
    # is not on sys.path. Ensure the project root is available so the
    # fallback imports succeed.
    pkg_root = os.path.dirname(os.path.dirname(__file__))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)

    from ui.settings_panel import SettingsPanel, build_stylesheet, DEFAULT_SHORTCUTS, DEFAULT_COLORS, DEFAULT_FONT
    from ui.video_window import VideoWindow
    from video.player import VideoEngine, SUPPORTED_VIDEO_FORMATS
    from ui.theme import STYLESHEET
    from ui.playlist_widget import FavoriteButton, PlaylistWidget
    from ui.playlist_manager_panel import PlaylistManagerPanel
    from ui.spatial_panel import SpatialPanel
    from ui.rotation_panel import RotationPanel
    from ui.vinyl_panel import VinylPanel
    from ui.visualizer_widget import SolarVisualizer, N_BANDS as VIZ_N_BANDS
    from ui.progress_widget import ClickableProgressSlider, IntensityProgressBar
    from core.playlist import Playlist, PlayMode, Track
    from core.session import SessionManager, SessionState, WindowState
    from core.playlist_manager import PlaylistManager
    from core.custom_playlist import CustomTrack, MoodEnum
    from core.startup import set_launch_at_startup
    from audio.engine import AudioEngine, SpatialConfig
    from ui.equalizer_panel import EqualizerPanel
    from audio.cd import parse_cd_uri
    from audio.cd_metadata import get_cached_cover_for_drive
    from core.library_scanner import scan_library_folders
    from ui.progress_dialog import TaskWorker
    from audio.preview_player import PreviewPlayer
    from audio.metadata import format_duration, read_metadata, read_cover_art_data
    from core.error_logging import append_error_log
    from core.volume import SLIDER_MAX, gain_to_slider_value, slider_to_gain
    from core.i18n import tr, set_language, get_language, DEFAULT_LANGUAGE


class DetachableTabBar(QTabBar):
    """TabBar qui permet de détacher un onglet en double-cliquant dessus."""
    detach_requested = pyqtSignal(int)

    def mouseDoubleClickEvent(self, event):
        idx = self.tabAt(event.pos())
        if idx >= 0:
            self.detach_requested.emit(idx)
        super().mouseDoubleClickEvent(event)


class DetachableTabWidget(QTabWidget):
    """
    QTabWidget dont chaque onglet peut être :
    - Détaché en une fenêtre flottante (double-clic sur l'onglet)
    - Réattaché par fermeture de la fenêtre flottante
    - Réordonné par drag & drop (QTabBar natif)
    L'onglet vidéo est toujours présent et non-fermable.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tab_bar = DetachableTabBar()
        self._tab_bar.detach_requested.connect(self._on_detach)
        self.setTabBar(self._tab_bar)
        self.setMovable(True)      # réordonnement drag & drop
        self.setTabsClosable(False)
        self._detached_windows: dict = {}  # idx_tab → QWidget fenêtre

    def _on_detach(self, index: int):
        if index < 0 or index >= self.count():
            return
        # Ne pas détacher si déjà détaché
        tab_text = self.tabText(index)
        if tab_text in self._detached_windows:
            self._detached_windows[tab_text].raise_()
            return

        widget = self.widget(index)
        if widget is None:
            return

        # Créer une fenêtre flottante
        win = QWidget()
        win.setWindowTitle(f"SolarSound — {tab_text.strip()}")
        win.resize(700, 500)
        layout = QVBoxLayout(win)
        layout.setContentsMargins(0, 0, 0, 0)

        # Retirer le widget de l'onglet et le mettre dans la fenêtre
        self.removeTab(index)
        layout.addWidget(widget)
        widget.setParent(win)

        self._detached_windows[tab_text] = win

        # Réattacher à la fermeture
        def on_close(event, tw=tab_text, w=widget, lbl=tab_text):
            w.setParent(self)
            self.addTab(w, lbl)
            del self._detached_windows[tw]
            event.accept()

        win.closeEvent = on_close
        win.show()


class _HoverProgressDelegate(QStyledItemDelegate):
    """
    Dessine une fine barre colorée en bas de la ligne survolée dans
    SearchResultsPopup, sous le texte normal de l'item :
      - pendant l'attente avant l'extrait : la barre se remplit de gauche
        à droite, jusqu'à HOVER_DELAY_MS (matérialise le compte à rebours) ;
      - pendant la lecture de l'extrait : un segment glissant en boucle,
        visuellement distinct, indique que l'aperçu est en cours.
    """

    BAR_HEIGHT = 3

    def __init__(self, popup, parent=None):
        super().__init__(parent)
        self._popup = popup

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        popup = self._popup
        item = popup.item(index.row())
        if item is None or item is not popup._hovered_item or popup._hover_state == "idle":
            return

        rect = option.rect
        bar_rect = QRect(rect.left(), rect.bottom() - self.BAR_HEIGHT + 1,
                          rect.width(), self.BAR_HEIGHT)
        accent = popup._accent_color
        track = QColor(accent.red(), accent.green(), accent.blue(), 55)
        elapsed = max(0.0, time.monotonic() - popup._hover_start_time)

        painter.save()
        painter.fillRect(bar_rect, track)

        if popup._hover_state == "waiting":
            duration = max(0.05, popup.HOVER_DELAY_MS / 1000.0)
            fraction = min(1.0, elapsed / duration)
            filled_w = int(bar_rect.width() * fraction)
            if filled_w > 0:
                painter.fillRect(QRect(bar_rect.left(), bar_rect.top(), filled_w, bar_rect.height()), accent)
        elif popup._hover_state == "playing":
            period = 1.1  # secondes pour un aller simple du segment
            seg_w = max(24, int(bar_rect.width() * 0.28))
            travel = bar_rect.width() + seg_w
            phase = (elapsed % period) / period
            x = bar_rect.left() - seg_w + int(phase * travel)
            seg_rect = QRect(x, bar_rect.top(), seg_w, bar_rect.height()).intersected(bar_rect)
            if not seg_rect.isEmpty():
                painter.fillRect(seg_rect, accent)

        painter.restore()


class SearchResultsPopup(QListWidget):
    """
    Liste déroulante des résultats de recherche (pistes/albums/artistes/
    playlists), affichée sous le champ de recherche de la barre de menus.

    Utilise Qt.WindowType.ToolTip + WA_ShowWithoutActivating (et non
    Qt.WindowType.Popup) pour ne JAMAIS voler le focus clavier au champ de
    recherche : un Popup Qt fait un grab clavier implicite dès qu'il
    s'affiche, ce qui empêchait de taper plus d'un caractère. Un ToolTip ne
    prend jamais le focus, donc la frappe continue normalement dans le champ.
    """

    result_activated = pyqtSignal(dict)
    hover_preview_requested = pyqtSignal(dict)  # survol > 1.5s d'un résultat
    hover_preview_cancelled = pyqtSignal()       # fin du survol / fermeture

    HOVER_DELAY_MS = 1500

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setIconSize(QSize(32, 32))
        self.setMouseTracking(True)
        self.setStyleSheet(
            "QListWidget { border: 1px solid #5a4a28; }"
            "QListWidget::item { padding: 4px 6px; }"
        )
        self.itemClicked.connect(self._on_item_clicked)
        self.itemEntered.connect(self._on_item_entered)

        self._hovered_item = None
        self._hover_state = "idle"   # "idle" | "waiting" | "playing"
        self._hover_start_time = 0.0
        self._accent_color = QColor("#f5a623")

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(self.HOVER_DELAY_MS)
        self._hover_timer.timeout.connect(self._on_hover_timeout)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)  # ~30 fps, suffisant pour une barre fine
        self._anim_timer.timeout.connect(self.viewport().update)

        self.setItemDelegate(_HoverProgressDelegate(self, self))

    def set_accent_color(self, color):
        """Aligne la couleur de l'animation sur le thème courant."""
        self._accent_color = QColor(color) if not isinstance(color, QColor) else color

    def _set_hover_state(self, state: str):
        self._hover_state = state
        self._hover_start_time = time.monotonic()
        if state == "idle":
            self._anim_timer.stop()
            self.viewport().update()
        elif not self._anim_timer.isActive():
            self._anim_timer.start()

    def _on_item_clicked(self, item):
        payload = item.data(Qt.ItemDataRole.UserRole)
        if payload:
            self.result_activated.emit(payload)
        self.hide()

    def _on_item_entered(self, item):
        if item is self._hovered_item:
            return
        self._hovered_item = item
        self._hover_timer.stop()
        self._set_hover_state("idle")
        self.hover_preview_cancelled.emit()
        if item.data(Qt.ItemDataRole.UserRole):
            self._hover_timer.start()
            self._set_hover_state("waiting")

    def _on_hover_timeout(self):
        if self._hovered_item:
            payload = self._hovered_item.data(Qt.ItemDataRole.UserRole)
            if payload:
                self._set_hover_state("playing")
                self.hover_preview_requested.emit(payload)

    def leaveEvent(self, event):
        self._hover_timer.stop()
        self._hovered_item = None
        self._set_hover_state("idle")
        self.hover_preview_cancelled.emit()
        super().leaveEvent(event)

    def hide(self):
        self._hover_timer.stop()
        self._hovered_item = None
        self._set_hover_state("idle")
        self.hover_preview_cancelled.emit()
        super().hide()

    def add_header(self, text: str):
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        self.addItem(item)

    def add_result(self, text: str, subtitle: str, icon, payload: dict):
        label = text if not subtitle else f"{text}  —  {subtitle}"
        item = QListWidgetItem(label)
        if icon:
            item.setIcon(icon)
        item.setData(Qt.ItemDataRole.UserRole, payload)
        self.addItem(item)

    def show_below(self, widget):
        pos = widget.mapToGlobal(QPoint(0, widget.height()))
        width = max(widget.width(), 380)

        screen = widget.screen() if hasattr(widget, "screen") else None
        if screen:
            available = screen.availableGeometry()
            # Ne jamais déborder sur l'écran voisin ni hors de l'écran courant
            max_x = available.right() - width
            pos.setX(min(max(pos.x(), available.left()), max(max_x, available.left())))
            max_height = max(150, available.bottom() - pos.y() - 10)
            self.setMaximumHeight(max_height)
        self.move(pos)
        self.setFixedWidth(width)
        self.show()


class MainWindow(QMainWindow):
    def __init__(self, open_files: List[str] = None):
        super().__init__()
        self.playlist = Playlist()
        self.engine = AudioEngine()
        self._current_track = None
        self._current_media_path = None
        self._is_handling_error = False
        self._playlist_drop_cursor_active = False
        self.engine.on_position_changed = self._on_position_changed
        self.engine.on_track_ended = self._on_track_ended
        self.engine.on_error = self._on_engine_error

        self._seeking = False
        self._last_position = 0.0
        self._session = SessionManager()

        # Playlists personnalisées avec humeurs (Mes Playlists)
        self.playlist_manager = PlaylistManager()
        self.playlist_manager.load_all()

        # Sauvegarde périodique de la position de lecture (indépendante du
        # debounce déclenché par les changements ponctuels d'état)
        self._position_save_timer = QTimer(self)
        self._position_save_timer.setInterval(10000)
        self._position_save_timer.timeout.connect(self._schedule_save)
        self._position_save_timer.start()

        # Dossiers de musique locaux (Paramètres → Bibliothèque) : élargissent
        # la recherche aux fichiers non encore ajoutés à une playlist, et
        # servent à retrouver les pistes déplacées/renommées.
        self._library_folders: List[str] = []
        self._library_index_cache: list = []
        self._library_index_last_ui_update = 0.0
        self._preview_player = PreviewPlayer()
        # État de la pause automatique du lecteur principal pendant un
        # extrait de recherche (voir _on_search_hover_preview) :
        self._preview_paused_audio = False  # AudioEngine mis en pause pour l'extrait
        self._preview_paused_video = False  # VideoEngine idem
        self._preview_resume_timer = QTimer(self)
        self._preview_resume_timer.setSingleShot(True)
        self._preview_resume_timer.timeout.connect(self._resume_main_after_preview)

        # Géométrie normale (hors minimisé) — mise à jour via changeEvent/moveEvent/resizeEvent
        self._normal_geometry = None

        # Timer débounce : sauvegarde 800ms après le dernier changement
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self._save_session)

        self._icons_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons")

        # Moteur vidéo (QObject — thread Qt principal requis)
        self.video_engine = VideoEngine(audio_engine=self.engine, parent=self)
        self.video_engine.on_track_ended = self._on_video_ended
        self.video_engine.on_error = self._on_engine_error

        # Paramètres UI (raccourcis, couleurs, polices)
        self._shortcuts = dict(DEFAULT_SHORTCUTS)
        self._colors    = dict(DEFAULT_COLORS)
        self._font_cfg  = dict(DEFAULT_FONT)
        self._progress_style = "classic"
        self._startup_config = {"enabled": False, "mode": "none", "value": ""}
        self._last_theme_colors = dict(DEFAULT_COLORS)

        # Mode courant : 'audio' ou 'video'
        self._media_mode = 'audio'

        self.setWindowTitle("SolarSound")
        self.setWindowIcon(QIcon(self._icon_path("solarsound.ico")))
        self.setMinimumSize(900, 680)
        self.setStyleSheet(build_stylesheet(self._colors, self._font_cfg))

        # Charger la session tôt pour appliquer la langue choisie AVANT de
        # construire l'UI : sinon les onglets seraient créés en français puis
        # retraduits, ce qui se voit au démarrage.
        session = self._session.load()
        self._startup_config = {
            "enabled": getattr(session, "startup_enabled", False),
            "mode": getattr(session, "startup_mode", "none"),
            "value": getattr(session, "startup_value", ""),
        }
        set_language(getattr(session, "language", DEFAULT_LANGUAGE))

        self._build_ui()
        # Autoriser le glisser-déposer sur la fenêtre principale
        self.setAcceptDrops(True)
        self._build_menu()
        self._build_status_bar()
        self._setup_timer()

        # Restaurer le reste de la session
        self._restore_session(session)

        # Fichiers ouverts via "Lire avec" ou argument CLI
        if open_files:
            self._open_files_from_args(open_files)

    # ── Glisser-déposer global (redirige vers _open_files_from_args) ──
    def _playlists_tab_active(self):
        return (
            hasattr(self, "_tabs")
            and hasattr(self, "playlist_manager_panel")
            and self._tabs.currentWidget() is self.playlist_manager_panel
        )

    @staticmethod
    def _folder_paths_from_drop(event):
        if not event.mimeData().hasUrls():
            return []
        return [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.toLocalFile() and os.path.isdir(url.toLocalFile())
        ]

    def _set_playlist_drop_cursor(self, active):
        if active and not self._playlist_drop_cursor_active:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.DragCopyCursor))
            self._playlist_drop_cursor_active = True
        elif not active and self._playlist_drop_cursor_active:
            QApplication.restoreOverrideCursor()
            self._playlist_drop_cursor_active = False

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if self._playlists_tab_active() and self._folder_paths_from_drop(event):
            self._set_playlist_drop_cursor(True)
            event.acceptProposedAction()
            return
        if md.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._playlists_tab_active() and self._folder_paths_from_drop(event):
            self._set_playlist_drop_cursor(True)
            event.acceptProposedAction()
            return
        self._set_playlist_drop_cursor(False)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._set_playlist_drop_cursor(False)
        event.accept()

    def dropEvent(self, event):
        md = event.mimeData()
        if not md.hasUrls():
            return
        folder_paths = self._folder_paths_from_drop(event)
        if self._playlists_tab_active() and folder_paths:
            self._set_playlist_drop_cursor(False)
            self.playlist_manager_panel.handle_external_folder_drop(folder_paths)
            event.acceptProposedAction()
            return
        self._set_playlist_drop_cursor(False)
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
                        if any(ext.endswith(e) for e in self.playlist.ALL_FORMATS):
                            paths.append(os.path.join(root, f))
            else:
                paths.append(local)

        if paths:
            self._open_files_from_args(paths)

    def _icon_path(self, name):
        return os.path.join(self._icons_dir, name)

    def _resync_local_styles(self, colors):
        """Remplace les anciennes couleurs littérales des styles locaux."""
        aliases = {
            "#f5a623": "accent", "#f5c842": "accent", "#ffbe4d": "accent",
            "#c47d0a": "accent_dark", "#e8d5a0": "text_primary",
            "#a08060": "text_secondary", "#7a6840": "text_secondary",
            "#5a4a28": "text_muted", "#3d3420": "border_bright",
            "#2a2416": "border", "#1e1a12": "btn_bg", "#0f0d0a": "bg_main",
            "#0c0a07": "bg_list", "#2a2008": "highlight_bg", "#202020": "bg_main",
        }
        replacements = {}
        replacements["rgba(245,166,35,"] = self._rgba_prefix(colors.get("accent", DEFAULT_COLORS["accent"]))
        replacements["rgba(10,8,6,"] = self._rgba_prefix(colors.get("bg_main", DEFAULT_COLORS["bg_main"]))
        previous = getattr(self, "_last_theme_colors", DEFAULT_COLORS)
        for old, key in aliases.items():
            replacements[old] = colors.get(key, DEFAULT_COLORS[key])
            replacements[previous.get(key, DEFAULT_COLORS[key])] = colors.get(key, DEFAULT_COLORS[key])

        for key, old in previous.items():
            if key not in DEFAULT_COLORS:
                continue
            old_color = QColor(old)
            new_color = QColor(colors.get(key, DEFAULT_COLORS[key]))
            if old_color.isValid() and new_color.isValid():
                old_rgb = f"rgba({old_color.red()},{old_color.green()},{old_color.blue()},"
                new_rgb = f"rgba({new_color.red()},{new_color.green()},{new_color.blue()},"
                replacements[old_rgb] = new_rgb

        for widget in self.findChildren(QWidget):
            style = widget.styleSheet()
            for old, new in replacements.items():
                style = style.replace(old, new)
            if style != widget.styleSheet():
                widget.setStyleSheet(style)
        self._last_theme_colors = dict(colors)

    @staticmethod
    def _rgba_prefix(color):
        value = QColor(color)
        return f"rgba({value.red()},{value.green()},{value.blue()}," if value.isValid() else "rgba(245,166,35,"

    def _tinted_icon(self, name, color):
        """Rend un SVG monochrome avec la couleur d'accent actuelle."""
        path = self._icon_path(name)
        if not name or not os.path.isfile(path):
            return QIcon()
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        QSvgRenderer(path).render(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
        painter.end()
        return QIcon(pixmap)

    def _refresh_transport_icons(self):
        accent = self._colors.get("accent", DEFAULT_COLORS["accent"])
        button_background = QColor(self._colors.get("btn_bg", DEFAULT_COLORS["btn_bg"]))
        play_color = "#ffffff" if button_background.lightness() > 150 else button_background.name()
        for button, name in (
            (self.btn_order, "sequential.svg"), (self.btn_loop, "boucle.svg"),
            (self.btn_prev, "preview.svg"), (self.btn_stop, "stop.svg"),
            (self.btn_next, "next.svg"),
        ):
            button.setIcon(self._tinted_icon(name, accent))
        self.btn_play.setIcon(self._tinted_icon("play.svg", play_color))
        self._refresh_favorites_ui()

    def _set_play_icon(self, playing: bool):
        button_background = QColor(self._colors.get("btn_bg", DEFAULT_COLORS["btn_bg"]))
        icon_color = "#ffffff" if button_background.lightness() > 150 else button_background.name()
        icon_name = "pause.svg" if playing else "play.svg"
        self.btn_play.setIcon(self._tinted_icon(icon_name, icon_color))

    # ══════════════════════════════════════════════════════════════════
    # SESSION — Sauvegarde / Restauration
    # ══════════════════════════════════════════════════════════════════

    def _save_session(self):
        """Sauvegarde l'état courant (appelé par le timer débounce et à la fermeture)."""
        # Utiliser la géométrie normale stockée (jamais celle de la fenêtre minimisée)
        if self._normal_geometry and not self.isMaximized():
            geo = self._normal_geometry
        elif self.isMaximized():
            # Maximisé : garder la dernière géométrie normale connue
            geo = self._normal_geometry or self.geometry()
        else:
            geo = self.geometry()

        screen = self.screen()
        screen_name = screen.name() if screen else ""

        win = WindowState(
            x=geo.x(),
            y=geo.y(),
            width=geo.width(),
            height=geo.height(),
            screen_name=screen_name,
            maximized=self.isMaximized(),
        )

        # Playlist : on sauvegarde les chemins
        tracks = [t.path for t in self.playlist.tracks]

        # Config spatiale
        cfg = self.engine.config
        spatial = {
            "gain_fl":  cfg.gain_fl,
            "gain_fr":  cfg.gain_fr,
            "gain_c":   cfg.gain_c,
            "gain_lfe": cfg.gain_lfe,
            "gain_sl":  cfg.gain_sl,
            "gain_sr":  cfg.gain_sr,
            "double_front_to_surround": cfg.double_front_to_surround,
            "surround_blend": cfg.surround_blend,
            "phase_to_surround": cfg.phase_to_surround,
            "phase_rear_blend": cfg.phase_rear_blend,
            "mix_to_lfe": cfg.mix_to_lfe,
            "lfe_low_pass_hz": cfg.lfe_low_pass_hz,
            "lfe_gain": cfg.lfe_gain,
            "master_volume": cfg.master_volume,
            "rotation_enabled": cfg.rotation_enabled,
            "rotation_speed": cfg.rotation_speed,
            "rotation_spread": cfg.rotation_spread,
            "stereo_separation": cfg.stereo_separation,
            "mix_mono": cfg.mix_mono,
            "invert_stereo": cfg.invert_stereo,
        }
        equalizer = dict(self.engine.equalizer_config.__dict__)

        # Config vinyle
        vinyl_cfg = {}
        if self.engine.vinyl:
            vc = self.engine.vinyl.config
            vinyl_cfg = {
                "enabled": vc.enabled, "motor_speed": vc.motor_speed,
                "motor_random": vc.motor_random, "wow_amount": vc.wow_amount,
                "wow_rate": vc.wow_rate, "flutter_amount": vc.flutter_amount,
                "flutter_rate": vc.flutter_rate, "crackle_density": vc.crackle_density,
                "crackle_amplitude": vc.crackle_amplitude,
                "crackle_duration_ms": vc.crackle_duration_ms, "hiss_level": vc.hiss_level,
            }

        state = SessionState(
            window=win,
            playlist_tracks=tracks,
            current_index=max(0, self.playlist.current_index),
            player_position=self.engine.position_seconds if self._media_mode == 'audio' else 0.0,
            play_mode=self.playlist.play_mode.name,
            current_tab=self._tabs.currentIndex(),
            volume=self.sld_volume.value(),
            output_device=self.engine.output_device,
            progress_style=self._progress_style,
            spatial_config=spatial,
            equalizer_config=equalizer,
        )
        state.vinyl_config = vinyl_cfg
        state.visualizer_enabled = self.visualizer.is_animation_enabled()
        state.startup_enabled = self._startup_config.get("enabled", False)
        state.startup_mode = self._startup_config.get("mode", "none")
        state.startup_value = self._startup_config.get("value", "")
        state.shortcuts = self._shortcuts
        state.colors    = self._colors
        state.font_cfg  = self._font_cfg
        state.library_folders = self._library_folders
        state.playlist_view_mode = self.playlist_manager_panel.get_view_mode()
        state.language = get_language()
        self._session.save(state)

    def _restore_session(self, state: SessionState):
        """Restaure la fenêtre, la playlist et les paramètres."""
        # ── Fenêtre & écran ──────────────────────────────────────────
        self._restore_window_geometry(state.window)

        # ── Paramètres d'interface ──────────────────────────────────
        self._shortcuts = {**DEFAULT_SHORTCUTS, **state.shortcuts}
        self._colors = {**DEFAULT_COLORS, **state.colors}
        self._font_cfg = {**DEFAULT_FONT, **state.font_cfg}
        self.settings_panel.apply_all(self._shortcuts, self._colors, self._font_cfg)
        self.setStyleSheet(build_stylesheet(self._colors, self._font_cfg))
        self._resync_local_styles(self._colors)
        self._apply_shortcuts()
        self.visualizer.set_theme_colors(self._colors)
        self._refresh_transport_icons()
        self.equalizer_panel.set_theme_colors(self._colors)
        self.spatial_panel.set_theme_colors(self._colors)
        self.rotation_panel.set_theme_colors(self._colors)
        if self.vinyl_panel is not None:
            self.vinyl_panel.set_theme_colors(self._colors)
        self.playlist_widget.set_theme_colors(self._colors)
        self.video_window.controls.set_theme_colors(self._colors)

        # ── Volume ───────────────────────────────────────────────────
        saved_value = state.volume
        slider_value = max(50, min(SLIDER_MAX, saved_value))
        self.sld_volume.setValue(slider_value)

        available_ids = {device[0] for device in self.engine.output_devices()}
        if state.output_device in available_ids:
            self.engine.output_device = state.output_device
            self.settings_panel.audio_tab.cmb_output.setCurrentIndex(
                self.settings_panel.audio_tab.cmb_output.findData(state.output_device)
            )
        self._set_progress_style(getattr(state, "progress_style", "classic"), emit=False)

        # ── Dossiers de musique (Bibliothèque) ──────────────────────
        self._library_folders = getattr(state, "library_folders", []) or []
        self.settings_panel.library_tab.set_folders(self._library_folders)
        self._rebuild_library_index()
        self.playlist_manager_panel.set_view_mode(getattr(state, "playlist_view_mode", "tree"))

        # ── Config spatiale ──────────────────────────────────────────
        if state.spatial_config:
            sc = state.spatial_config
            cfg = self.engine.config
            cfg.gain_fl  = sc.get("gain_fl",  1.0)
            cfg.gain_fr  = sc.get("gain_fr",  1.0)
            cfg.gain_c   = sc.get("gain_c",   0.0)
            cfg.gain_lfe = sc.get("gain_lfe", 0.8)
            cfg.gain_sl  = sc.get("gain_sl",  0.0)
            cfg.gain_sr  = sc.get("gain_sr",  0.0)
            cfg.double_front_to_surround = sc.get("double_front_to_surround", False)
            cfg.surround_blend = sc.get("surround_blend", 0.6)
            cfg.phase_to_surround = sc.get("phase_to_surround", False)
            cfg.phase_rear_blend = sc.get("phase_rear_blend", 0.8)
            cfg.mix_to_lfe = sc.get("mix_to_lfe", False)
            cfg.lfe_low_pass_hz = sc.get("lfe_low_pass_hz", 120.0)
            cfg.lfe_gain = sc.get("lfe_gain", 1.0)
            cfg.master_volume = sc.get("master_volume", 1.0)
            cfg.rotation_enabled = sc.get("rotation_enabled", False)
            cfg.rotation_speed   = sc.get("rotation_speed", 0.1)
            cfg.rotation_spread  = sc.get("rotation_spread", 0.5)
            self.engine.update_lpf()
            self.spatial_panel.apply_config(cfg)
            self.rotation_panel.apply_config(cfg)

        # ── Egaliseur ───────────────────────────────────────────────
        if state.equalizer_config:
            self.engine.equalizer_config.__dict__.update(state.equalizer_config)
            self.equalizer_panel.apply_config(state.equalizer_config)

        # ── Playlist ─────────────────────────────────────────────────
        if state.playlist_tracks:
            valid_paths = [
                p for p in state.playlist_tracks
                if os.path.isfile(p) or parse_cd_uri(p)
            ]
            if valid_paths:
                self.playlist_widget.restore_files_async(valid_paths)
                idx = min(state.current_index, len(self.playlist.tracks) - 1)
                track = self.playlist.set_current(idx)
                self.playlist_widget.set_active_row(idx)

                # Recharger la piste courante (sans lancer la lecture) et
                # reprendre à la même position qu'à la fermeture.
                if track and not self._is_video(track.path):
                    self._current_track = track
                    self._current_media_path = track.path
                    if self.engine.load(track.path):
                        pos = max(0.0, min(
                            getattr(state, "player_position", 0.0),
                            self.engine.duration_seconds,
                        ))
                        self.engine.seek(pos)
                        is_cd = parse_cd_uri(track.path) is not None
                        self._update_progress_stack_for_track(is_cd)
                        if not is_cd:
                            self.intensity_progress.set_levels(self.engine.get_timeline_levels(240))
                        self._update_track_display(track)
                        dur = self.engine.duration_seconds
                        self.lbl_dur.setText(format_duration(dur))
                        self.lbl_pos.setText(format_duration(pos))
                        if dur > 0:
                            self.sld_progress.setValue(int(pos / dur * 1000))
                        self.status_bar.showMessage(f"Reprise : {track.title}")

        # ── Animation du visualiseur ────────────────────────────────
        enabled = getattr(state, "visualizer_enabled", True)
        self.visualizer.set_enabled_animation(enabled, emit=False)
        self.act_visualizer.setChecked(enabled)

        # ── Mode de lecture ──────────────────────────────────────────
        try:
            mode = PlayMode[state.play_mode]
        except KeyError:
            mode = PlayMode.SEQUENTIAL
        self._set_play_mode(mode)
        if 0 <= state.current_tab < self._tabs.count():
            self._tabs.setCurrentIndex(state.current_tab)

    def _restore_window_geometry(self, win: WindowState):
        """Place la fenêtre sur le bon écran, à la bonne taille."""
        screens = QApplication.screens()

        # Trouver l'écran cible par nom
        target_screen = None
        for s in screens:
            if s.name() == win.screen_name:
                target_screen = s
                break
        if target_screen is None and screens:
            target_screen = screens[0]

        if target_screen:
            screen_geo = target_screen.geometry()
            # Vérifier que la position est toujours valide sur cet écran
            x = win.x
            y = win.y
            w = max(900, win.width)
            h = max(680, win.height)

            # Si la fenêtre est complètement hors de l'écran, la recentrer
            if not screen_geo.contains(x + 50, y + 50):
                x = screen_geo.x() + (screen_geo.width() - w) // 2
                y = screen_geo.y() + (screen_geo.height() - h) // 2

            self.setGeometry(x, y, w, h)
        else:
            self.resize(win.width, win.height)

        if win.maximized:
            self.showMaximized()

    def _schedule_save(self):
        """Déclenche une sauvegarde différée (débounce 800ms)."""
        self._save_timer.start()

    # ── Suivi de la géométrie normale de la fenêtre ───────────────────
    def changeEvent(self, event):
        """Détecte la minimisation / restauration."""
        from PyQt6.QtCore import QEvent
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if not (self.isMinimized() or self.isMaximized()):
                # Fenêtre restaurée en taille normale : capturer la géométrie
                self._normal_geometry = self.geometry()

    def resizeEvent(self, event):
        """Capture la taille normale et programme une sauvegarde."""
        super().resizeEvent(event)
        if not self.isMinimized() and not self.isMaximized():
            self._normal_geometry = self.geometry()
            self._schedule_save()

    def moveEvent(self, event):
        """Capture la position normale et programme une sauvegarde."""
        super().moveEvent(event)
        if not self.isMinimized() and not self.isMaximized():
            self._normal_geometry = self.geometry()
            self._schedule_save()

    # ══════════════════════════════════════════════════════════════════
    # OUVERTURE VIA "LIRE AVEC"
    # ══════════════════════════════════════════════════════════════════

    def _open_files_from_args(self, paths: List[str]):
        """
        Ouvre les fichiers passés en argument CLI.
        - .playlist → charge la playlist et démarre la lecture
        - .mp3/.wav → ajoute à la playlist et démarre immédiatement
        - vidéo → ajoute et lance le lecteur vidéo
        """
        playlist_files = [p for p in paths if p.lower().endswith(".playlist")]
        audio_files    = [p for p in paths if os.path.splitext(p)[1].lower() in Playlist.SUPPORTED_FORMATS]
        video_files    = [p for p in paths if any(
            p.lower().endswith(ext) for ext in SUPPORTED_VIDEO_FORMATS
        )]

        if playlist_files:
            # Charger la première playlist trouvée
            try:
                self.playlist.load(playlist_files[0])
                self.playlist_widget.refresh_from_playlist()
                if self.playlist.tracks:
                    track = self.playlist.current_track or self.playlist.set_current(0)
                    if track:
                        self._load_and_play(track, self.playlist.current_index)
            except Exception as e:
                self.status_bar.showMessage(f"Erreur chargement playlist : {e}")

        elif audio_files:
            self.playlist_widget._add_files(audio_files)
            if self.playlist.tracks:
                first_path = audio_files[0]
                for i, t in enumerate(self.playlist.tracks):
                    if t.path == first_path:
                        track = self.playlist.set_current(i)
                        self._load_and_play(track, i)
                        break
        elif video_files:
            self.playlist_widget._add_files(video_files)
            if self.playlist.tracks:
                first_path = video_files[0]
                for i, t in enumerate(self.playlist.tracks):
                    if t.path == first_path:
                        self.playlist.set_current(i)
                        self._load_and_play_video(t.path)
                        break

    # ══════════════════════════════════════════════════════════════════
    # Construction UI
    # ══════════════════════════════════════════════════════════════════
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(8)

        header = self._build_header()
        root.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2416;")
        root.addWidget(sep)

        track_area = self._build_track_area()
        root.addLayout(track_area)

        progress_area = self._build_progress()
        root.addLayout(progress_area)

        transport = self._build_transport()
        root.addLayout(transport)

        self._tabs = self._build_tabs()
        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs, stretch=1)
        self._refresh_favorites_ui()

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        lbl_title = QLabel("SOLAR")
        lbl_title.setObjectName("title_label")
        lbl_title.setStyleSheet(
            "font-size: 26px; font-weight: 900; letter-spacing: 4px;"
        )

        lbl_sound = QLabel("SOUND")
        lbl_sound.setObjectName("sound_label")
        lbl_sound.setStyleSheet(
            "font-size: 26px; font-weight: 300; letter-spacing: 4px;"
        )

        lbl_sub = QLabel("LECTEUR 5.1")
        lbl_sub.setObjectName("subtitle_label")
        lbl_sub.setStyleSheet(
            "font-size: 10px; letter-spacing: 6px; margin-left: 4px;"
        )

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sound)
        layout.addWidget(lbl_sub)
        layout.addStretch()

        self.lbl_mode_indicator = QLabel("⬤ STÉRÉO")
        self.lbl_mode_indicator.setStyleSheet(
            "font-size: 11px; color: #5a4a28; letter-spacing: 2px;"
        )
        layout.addWidget(self.lbl_mode_indicator)

        return layout

    def _build_track_area(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(16)

        self.art_frame = QFrame()
        self.art_frame.setFixedSize(80, 80)
        self.art_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e1a12, stop:1 #2a2008
                );
                border: 1px solid #3d3420;
                border-radius: 6px;
            }
        """)
        art_inner = QVBoxLayout(self.art_frame)
        art_inner.setContentsMargins(0, 0, 0, 0)
        self.art_label = QLabel("♪")
        self.art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_label.setStyleSheet("font-size: 32px; color: #3d3420; border: none; background: transparent;")
        self.art_label.setFixedSize(80, 80)
        art_inner.addWidget(self.art_label)
        layout.addWidget(self.art_frame)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setContentsMargins(0, 8, 0, 0)

        self.lbl_title = QLabel("Aucun morceau")
        self.lbl_title.setObjectName("track_title")
        self.lbl_title.setStyleSheet("font-size: 17px; font-weight: bold;")
        self.lbl_title.setWordWrap(False)
        info_col.addWidget(self.lbl_title)

        self.lbl_artist = QLabel("—")
        self.lbl_artist.setObjectName("track_artist")
        self.lbl_artist.setStyleSheet("font-size: 13px;")
        info_col.addWidget(self.lbl_artist)

        self.lbl_album = QLabel("")
        self.lbl_album.setStyleSheet("font-size: 11px; color: #5a4a28;")
        info_col.addWidget(self.lbl_album)

        info_col.addStretch()
        layout.addLayout(info_col, stretch=1)

        self.visualizer = SolarVisualizer(
            levels_provider=lambda: self.engine.get_visual_levels(VIZ_N_BANDS)
        )
        layout.addWidget(self.visualizer, stretch=2, alignment=Qt.AlignmentFlag.AlignVCenter)

        vol_col = QVBoxLayout()
        vol_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        vol_col.setSpacing(4)

        lbl_vol = QLabel("VOL")
        lbl_vol.setStyleSheet("font-size: 10px; color: #5a4a28; letter-spacing: 2px;")
        lbl_vol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vol_col.addWidget(lbl_vol)

        self.sld_volume = QSlider(Qt.Orientation.Vertical)
        self.sld_volume.setRange(50, SLIDER_MAX)
        self.sld_volume.setValue(gain_to_slider_value(1.0))
        self.sld_volume.setFixedHeight(70)
        self.sld_volume.setToolTip("Volume principal")
        self.sld_volume.valueChanged.connect(self._on_volume_changed)
        vol_col.addWidget(self.sld_volume, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.lbl_vol_val = QLabel("100%")
        self.lbl_vol_val.setStyleSheet("font-size: 10px; color: #7a6840;")
        self.lbl_vol_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vol_col.addWidget(self.lbl_vol_val)

        layout.addLayout(vol_col)
        return layout

    def _build_progress(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)

        self.lbl_pos = QLabel("0:00")
        self.lbl_pos.setObjectName("time_label")
        self.lbl_pos.setFixedWidth(45)
        self.lbl_pos.setStyleSheet("font-family: 'Consolas', monospace; color: #7a6840;")
        layout.addWidget(self.lbl_pos)

        self.sld_progress = ClickableProgressSlider(Qt.Orientation.Horizontal)
        self.sld_progress.setRange(0, 1000)
        self.sld_progress.setValue(0)
        self.sld_progress.sliderPressed.connect(self._on_seek_start)
        self.sld_progress.sliderMoved.connect(self._on_progress_dragged)
        self.sld_progress.sliderReleased.connect(self._on_seek_end)
        self.intensity_progress = IntensityProgressBar()
        self.intensity_progress.position_requested.connect(self._on_intensity_seek)
        self.intensity_progress.position_released.connect(self._on_intensity_seek_end)
        self.progress_stack = QStackedWidget()
        self.progress_stack.addWidget(self.sld_progress)
        self.progress_stack.addWidget(self.intensity_progress)
        layout.addWidget(self.progress_stack, stretch=1)

        self.lbl_dur = QLabel("0:00")
        self.lbl_dur.setObjectName("time_label")
        self.lbl_dur.setFixedWidth(45)
        self.lbl_dur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_dur.setStyleSheet("font-family: 'Consolas', monospace; color: #7a6840;")
        layout.addWidget(self.lbl_dur)

        return layout

    def _build_transport(self) -> QGridLayout:
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(0)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(4)

        self.btn_order = QPushButton()
        self.btn_order.setIcon(self._tinted_icon("sequential.svg", self._colors["accent"]))
        self.btn_order.setIconSize(QSize(18, 18))
        self.btn_order.setToolTip("Lecture séquentielle")
        self.btn_order.setCheckable(False)
        self.btn_order.setFixedSize(32, 32)

        self.btn_favorite_track = FavoriteButton(
            accent=self._colors["accent"], framed=True
        )
        self.btn_favorite_track.setToolTip("Ajouter le morceau aux coups de coeur")
        self.btn_favorite_track.setFixedSize(32, 32)
        self.btn_favorite_track.clicked.connect(self._on_current_track_favorite)

        self.btn_loop = QPushButton()
        self.btn_loop.setIcon(self._tinted_icon("boucle.svg", self._colors["accent"]))
        self.btn_loop.setIconSize(QSize(18, 18))
        self.btn_loop.setToolTip("Boucle sur toute la liste")
        self.btn_loop.setCheckable(False)
        self.btn_loop.setFixedSize(32, 32)

        self._order_mode = PlayMode.SEQUENTIAL
        self._loop_pref = PlayMode.LOOP_ALL
        self._sequential_loop_active = False

        mode_layout.addWidget(self.btn_loop)
        mode_layout.addWidget(self.btn_order)
        mode_layout.addWidget(self.btn_favorite_track)

        self.btn_order.clicked.connect(self._on_order_toggle)
        self.btn_loop.clicked.connect(self._on_loop_toggle)

        controls_layout.addLayout(mode_layout)
        controls_layout.addSpacing(24)

        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(self._tinted_icon("preview.svg", self._colors["accent"]))
        self.btn_prev.setIconSize(QSize(24, 24))
        self.btn_prev.setObjectName("btn_prev")
        self.btn_prev.setToolTip("Morceau précédent")
        self.btn_prev.clicked.connect(self._on_prev)
        controls_layout.addWidget(self.btn_prev)

        controls_layout.addSpacing(8)

        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(self._tinted_icon("stop.svg", self._colors["accent"]))
        self.btn_stop.setIconSize(QSize(24, 24))
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setToolTip("Stop")
        self.btn_stop.clicked.connect(self._on_stop)
        controls_layout.addWidget(self.btn_stop)

        controls_layout.addSpacing(8)

        self.btn_play = QPushButton()
        button_background = QColor(self._colors["btn_bg"])
        play_color = "#ffffff" if button_background.lightness() > 150 else button_background.name()
        self.btn_play.setIcon(self._tinted_icon("play.svg", play_color))
        self.btn_play.setIconSize(QSize(24, 24))
        self.btn_play.setObjectName("btn_play")
        self.btn_play.setToolTip("Lecture / Pause")
        self.btn_play.clicked.connect(self._on_play_pause)
        controls_layout.addWidget(self.btn_play)

        controls_layout.addSpacing(8)

        self.btn_next = QPushButton()
        self.btn_next.setIcon(self._tinted_icon("next.svg", self._colors["accent"]))
        self.btn_next.setIconSize(QSize(24, 24))
        self.btn_next.setObjectName("btn_next")
        self.btn_next.setToolTip("Morceau suivant")
        self.btn_next.clicked.connect(self._on_next)
        controls_layout.addWidget(self.btn_next)

        self.next_track_frame = QFrame()
        self.next_track_frame.setFixedSize(290, 62)
        self.next_track_frame.setStyleSheet(
            "QFrame { background-color: #0c0a07; border: 1px solid #3d3420; "
            "border-radius: 6px; }"
        )
        next_layout = QHBoxLayout(self.next_track_frame)
        next_layout.setContentsMargins(8, 5, 8, 5)
        next_layout.setSpacing(8)

        self.next_track_art = QLabel("♪")
        self.next_track_art.setFixedSize(46, 46)
        self.next_track_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_track_art.setStyleSheet(
            "font-size: 22px; color: #5a4a28; border: none; background: #1e1a12;"
        )
        next_layout.addWidget(self.next_track_art)

        next_info = QVBoxLayout()
        next_info.setContentsMargins(0, 0, 0, 0)
        next_info.setSpacing(1)
        self.lbl_next_prefix = QLabel("Prochain :")
        self.lbl_next_prefix.setStyleSheet(
            "font-size: 10px; color: #f5a623; border: none; background: transparent;"
        )
        self.lbl_next_title = QLabel("Aucun morceau")
        self.lbl_next_title.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #e8d5a0; border: none; background: transparent;"
        )
        self.lbl_next_title.setMaximumWidth(215)
        self.lbl_next_artist = QLabel("—")
        self.lbl_next_artist.setStyleSheet(
            "font-size: 10px; color: #a08060; border: none; background: transparent;"
        )
        self.lbl_next_artist.setMaximumWidth(215)
        next_info.addWidget(self.lbl_next_prefix)
        next_info.addWidget(self.lbl_next_title)
        next_info.addWidget(self.lbl_next_artist)
        next_layout.addLayout(next_info, stretch=1)
        controls_widget = QWidget()
        controls_widget.setLayout(controls_layout)

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(controls_widget, 0, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.next_track_frame, 0, 2, alignment=Qt.AlignmentFlag.AlignRight)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(2, 1)

        self._update_next_track_panel()

        return layout

    def _next_track_preview(self):
        tracks = self.playlist.tracks
        if not tracks:
            return None

        current_index = self.playlist.current_index
        if self.playlist.play_mode == PlayMode.LOOP_ONE:
            return self.playlist.current_track

        if self.playlist.play_mode == PlayMode.RANDOM:
            order = self.playlist._shuffle_order
            if not order:
                return tracks[0]
            position = self.playlist._shuffle_pos
            return tracks[order[(position + 1) % len(order)]]

        next_index = 0 if current_index < 0 else current_index + 1
        if next_index >= len(tracks):
            if self.playlist.play_mode != PlayMode.LOOP_ALL:
                return None
            next_index = 0
        return tracks[next_index]

    def _update_next_track_panel(self):
        if not hasattr(self, "next_track_art"):
            return
        track = self._next_track_preview()
        if track is None:
            self.next_track_art.clear()
            self.next_track_art.setText("♪")
            self.lbl_next_title.setText("Aucun morceau")
            self.lbl_next_artist.setText("—")
            return

        title = track.title or os.path.basename(track.path)
        artist = track.artist or "Artiste inconnu"
        icon = self._get_track_cover_icon(track)
        self.next_track_art.setText("")
        self.next_track_art.setPixmap(icon.pixmap(46, 46))
        self.lbl_next_title.setText(title)
        self.lbl_next_title.setToolTip(title)
        self.lbl_next_artist.setText(artist)
        self.lbl_next_artist.setToolTip(artist)

    def _build_tabs(self) -> DetachableTabWidget:
        tabs = DetachableTabWidget()

        # ── Playlist ──────────────────────────────────────────────────
        self.playlist_widget = PlaylistWidget(self.playlist)
        self.playlist_widget.track_activated.connect(self._on_track_activated)
        self.playlist_widget.playlist_changed.connect(self._on_playlist_changed)
        self.playlist_widget.restored_track_metadata.connect(self._on_restored_track_metadata)
        self.playlist_widget.mood_selected.connect(self._on_mood_selected)
        self.playlist_widget.favorite_toggled.connect(self._on_favorite_requested)
        self.playlist_widget.play_favorites_requested.connect(self._on_play_favorites)
        self.playlist_widget.open_playlist_manager.connect(self._on_open_playlist_manager)
        tabs.addTab(self.playlist_widget, tr("tab.playlist"))

        # ── Lecteur Vidéo (prioritaire, premier onglet clé) ───────────
        self.video_window = VideoWindow(self.video_engine, self._icons_dir)
        self.video_window.request_prev.connect(self._on_prev)
        self.video_window.request_next.connect(self._on_next)
        self.video_window.request_stop.connect(self._on_stop)
        tabs.addTab(self.video_window, tr("tab.video"))

        # ── Mes Playlists (playlists personnalisées avec humeurs) ─────
        self.playlist_manager_panel = PlaylistManagerPanel(
            self.playlist_manager, get_library_folders=lambda: self._library_folders
        )
        self.playlist_manager_panel.load_requested.connect(self._on_load_custom_playlist)
        self.playlist_manager_panel.load_folder_requested.connect(
            self._on_load_custom_folder
        )
        self._playlists_tab_index = 2
        tabs.insertTab(self._playlists_tab_index, self.playlist_manager_panel, tr("tab.my_playlists"))

        # ── Spatialisation ────────────────────────────────────────────
        self.spatial_panel = SpatialPanel(self.engine.config)
        self.spatial_panel.config_changed.connect(self._on_spatial_config_changed)
        tabs.addTab(self.spatial_panel, tr("tab.surround"))

        # ── Egaliseur ────────────────────────────────────────────────
        self.equalizer_panel = EqualizerPanel(self.engine.equalizer_config.__dict__)
        self.equalizer_panel.config_changed.connect(self._on_equalizer_config_changed)
        tabs.addTab(self.equalizer_panel, tr("tab.equalizer"))

        # ── Rotation ─────────────────────────────────────────────────
        self.rotation_panel = RotationPanel(self.engine.config)
        self.rotation_panel.config_changed.connect(self._on_spatial_config_changed)
        tabs.addTab(self.rotation_panel, tr("tab.rotation"))

        # ── Vinyle ────────────────────────────────────────────────────
        if self.engine.vinyl:
            self.vinyl_panel = VinylPanel(self.engine.vinyl.config)
            self.vinyl_panel.config_changed.connect(self._on_vinyl_config_changed)
            tabs.addTab(self.vinyl_panel, tr("tab.vinyl"))
        else:
            self.vinyl_panel = None

        # ── Paramètres ────────────────────────────────────────────────
        self.settings_panel = SettingsPanel(
            self._shortcuts, self._colors, self._font_cfg,
            self.engine.output_devices(), self.engine.output_device, self._progress_style,
            self._library_folders, get_language(), self._startup_config
        )
        self.settings_panel.output_changed.connect(self._on_output_changed)
        self.settings_panel.startup_changed.connect(self._on_startup_changed)
        self.settings_panel.progress_style_changed.connect(self._on_progress_style_changed)
        self.settings_panel.shortcuts_changed.connect(self._on_shortcuts_changed)
        self.settings_panel.colors_changed.connect(self._on_colors_changed)
        self.settings_panel.font_changed.connect(self._on_font_changed)
        self.settings_panel.folders_changed.connect(self._on_library_folders_changed)
        self.settings_panel.language_changed.connect(self._on_language_changed)
        self.settings_panel.startup_tab.set_sources(
            MoodEnum.get_all_moods(),
            [(p.name, p.id) for p in self.playlist_manager.get_all_playlists()],
            [(f.name, f.id) for f in self.playlist_manager.get_all_folders()],
        )
        tabs.addTab(self.settings_panel, tr("tab.settings"))

        # Activer l'onglet vidéo par défaut (index 1)
        tabs.setCurrentIndex(1)

        return tabs
    def _build_menu(self):
        mb = self.menuBar()
        self._shortcut_actions = {}

        file_menu = mb.addMenu("&Fichier")
        act_open = QAction("&Ouvrir des fichiers…", self)
        act_open.triggered.connect(self.playlist_widget._on_add_files)
        file_menu.addAction(act_open)
        self._shortcut_actions["open_file"] = act_open

        act_open_pl = QAction("Ouvrir une &liste…", self)
        act_open_pl.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_pl.triggered.connect(self.playlist_widget._on_load_playlist)
        file_menu.addAction(act_open_pl)

        act_save_pl = QAction("&Enregistrer la liste…", self)
        act_save_pl.triggered.connect(self.playlist_widget._on_save_playlist)
        file_menu.addAction(act_save_pl)

        file_menu.addSeparator()
        act_quit = QAction("&Quitter", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)
        self._shortcut_actions["close"] = act_quit

        play_menu = mb.addMenu("&Lecture")
        act_pp = QAction("Lecture / &Pause", self)
        act_pp.triggered.connect(self._on_play_pause)
        play_menu.addAction(act_pp)
        self._shortcut_actions["play_pause"] = act_pp

        act_stop = QAction("&Stop", self)
        act_stop.triggered.connect(self._on_stop)
        play_menu.addAction(act_stop)
        self._shortcut_actions["stop"] = act_stop

        act_next = QAction("&Suivant", self)
        act_next.triggered.connect(self._on_next)
        play_menu.addAction(act_next)
        self._shortcut_actions["next"] = act_next

        act_prev = QAction("&Précédent\n", self)
        act_prev.triggered.connect(self._on_prev)
        play_menu.addAction(act_prev)
        self._shortcut_actions["prev"] = act_prev

        view_menu = mb.addMenu("&Affichage")
        self.act_visualizer = QAction("&Animation solaire", self)
        self.act_visualizer.setCheckable(True)
        self.act_visualizer.setChecked(True)
        self.act_visualizer.setToolTip(
            "Désactiver pour économiser des ressources (raccourci : clic droit sur l'animation)"
        )
        self.act_visualizer.toggled.connect(self._on_visualizer_toggled)
        self.visualizer.toggled.connect(self.act_visualizer.setChecked)
        view_menu.addAction(self.act_visualizer)

        about_menu = mb.addMenu("&À propos")
        act_about = QAction("À &propos de SolarSound", self)
        act_about.triggered.connect(self._show_about)
        about_menu.addAction(act_about)

        # ── Recherche (pistes / albums / artistes / playlists) ────────
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("🔍 Rechercher pistes, albums, artistes, playlists…")
        self.search_field.setMinimumWidth(260)
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self._on_search_text_changed)
        self.search_field.installEventFilter(self)

        # Conteneur avec marges : le champ ne doit pas coller aux bords de
        # la barre de menus.
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(8, 4, 12, 4)
        search_layout.addWidget(self.search_field)

        self.search_popup = SearchResultsPopup(self)
        self.search_popup.set_accent_color(self._colors.get("accent", "#f5a623"))
        self.search_popup.result_activated.connect(self._on_search_result_activated)
        self.search_popup.hover_preview_requested.connect(self._on_search_hover_preview)
        self.search_popup.hover_preview_cancelled.connect(self._on_search_hover_preview_cancelled)

        mb.setCornerWidget(search_container, Qt.Corner.TopRightCorner)

    def _build_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(tr("status.ready"))

        # Petit indicateur discret (droite de la barre de statut) pour
        # l'indexation de la bibliothèque en arrière-plan : pas de fenêtre
        # modale, juste ce texte qui apparaît/disparaît tout seul.
        self.lbl_library_index_status = QLabel("")
        self.lbl_library_index_status.setStyleSheet("color: #8a7a58; font-size: 11px;")
        self.lbl_library_index_status.setVisible(False)
        self.status_bar.addPermanentWidget(self.lbl_library_index_status)

    # ══════════════════════════════════════════════════════════════════
    # Recherche (pistes / albums / artistes / playlists)
    # ══════════════════════════════════════════════════════════════════
    def _default_cover_pixmap(self, size):
        """Retourne la pochette par défaut SVG utilisée si aucune cover n'est disponible."""
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

    def _get_track_cover_icon(self, track):
        """Icône de pochette pour une piste (fichier local, tags embarqués, ou CD via cache)."""
        cover_data = read_cover_art_data(track.path)
        if not cover_data:
            cd_location = parse_cd_uri(track.path)
            if cd_location:
                drive, _ = cd_location
                cover_data = get_cached_cover_for_drive(drive)
        if not cover_data:
            return QIcon(self._default_cover_pixmap(QSize(64, 64)))
        pixmap = QPixmap()
        if pixmap.loadFromData(cover_data):
            return QIcon(pixmap)
        return QIcon(self._default_cover_pixmap(QSize(64, 64)))

    def _all_known_tracks_deduped(self):
        """Toutes les pistes connues (liste de lecture + playlists perso), sans doublon de chemin."""
        all_tracks = list(self.playlist.tracks)
        for cp in self.playlist_manager.get_all_playlists():
            all_tracks.extend(cp.tracks)

        seen_paths = set()
        unique_tracks = []
        for t in all_tracks:
            if t.path in seen_paths:
                continue
            seen_paths.add(t.path)
            unique_tracks.append(t)

        # Fichiers des dossiers de musique configurés (Paramètres →
        # Bibliothèque) pas encore ajoutés à une playlist : élargit la
        # recherche à toute la bibliothèque locale, pas seulement à ce qui
        # est déjà en playlist.
        for entry in self._library_index_cache:
            if entry["path"] in seen_paths:
                continue
            seen_paths.add(entry["path"])
            unique_tracks.append(Track(
                path=entry["path"],
                title=entry.get("title") or os.path.basename(entry["path"]),
                artist=entry.get("artist", ""),
                album=entry.get("album", ""),
                duration=entry.get("duration", 0.0),
            ))

        return unique_tracks

    def _rebuild_library_index(self):
        """
        Réindexe les dossiers de musique configurés (utilisé par la
        recherche), en arrière-plan et sans aucune fenêtre : juste un
        petit texte discret dans le coin droit de la barre de statut,
        pour ne jamais bloquer le démarrage ni l'interface.
        """
        if not self._library_folders:
            self._library_index_cache = []
            return

        # Garder une référence sur self pour éviter que le thread ne soit
        # ramassé par le GC pendant son exécution.
        self._library_index_worker = TaskWorker(scan_library_folders, folders=self._library_folders)
        self._library_index_worker.progress.connect(self._on_library_index_progress)
        self._library_index_worker.finished_with_result.connect(self._on_library_index_ready)
        self._library_index_worker.failed.connect(self._on_library_index_error)

        self.lbl_library_index_status.setStyleSheet("color: #8a7a58; font-size: 11px;")
        self.lbl_library_index_status.setText("⏳ " + tr("library.indexing"))
        self.lbl_library_index_status.setVisible(True)

        self._library_index_worker.start()

    def _on_library_index_progress(self, current: int, total: int, message: str):
        """Compteur discret « ⏳ Indexation… 120/480 » dans la barre de statut.

        scan_library_folders() émet un premier report(0, total, …) une fois
        les fichiers listés, puis un report par fichier analysé. Sur une
        grosse bibliothèque ça fait des milliers d'appels : on limite le
        rafraîchissement à ~10 par seconde pour ne pas saturer l'UI.
        """
        now = time.monotonic()
        is_edge = current <= 0 or current >= total
        if not is_edge and (now - self._library_index_last_ui_update) < 0.1:
            return
        self._library_index_last_ui_update = now

        if total > 0:
            self.lbl_library_index_status.setText(
                "⏳ " + tr("library.indexing_count", current=current, total=total)
            )
        else:
            self.lbl_library_index_status.setText("⏳ " + tr("library.indexing"))

    def _on_library_index_ready(self, index: list):
        self._library_index_cache = index
        self.lbl_library_index_status.setVisible(False)

    def _on_library_index_error(self, message: str):
        self._library_index_cache = []
        self.lbl_library_index_status.setStyleSheet("color: #b06a3a; font-size: 11px;")
        self.lbl_library_index_status.setText("⚠ " + tr("library.index_failed"))
        QTimer.singleShot(5000, lambda: self.lbl_library_index_status.setVisible(False))

    def _on_language_changed(self, code: str):
        """Applique la nouvelle langue et retraduit ce qui peut l'être à chaud."""
        set_language(code)
        self._retranslate_ui()
        self._schedule_save()

    def _retranslate_ui(self):
        """Remet à jour les textes déjà affichés après un changement de langue.

        Seuls les libellés reconstruits ici changent sans redémarrage ; les
        panneaux qui utilisent encore des chaînes en dur garderont leur texte
        jusqu'au prochain lancement (d'où l'avertissement dans l'onglet Langue).
        """
        tabs = self._tabs
        titles = [
            ("tab.playlist", self.playlist_widget),
            ("tab.video", self.video_window),
            ("tab.my_playlists", self.playlist_manager_panel),
            ("tab.surround", self.spatial_panel),
            ("tab.equalizer", self.equalizer_panel),
            ("tab.rotation", self.rotation_panel),
            ("tab.vinyl", getattr(self, "vinyl_panel", None)),
            ("tab.settings", self.settings_panel),
        ]
        for key, widget in titles:
            if widget is None:
                continue
            index = tabs.indexOf(widget)
            if index >= 0:
                tabs.setTabText(index, tr(key))

        self.status_bar.showMessage(tr("status.ready"))
        self.settings_panel.retranslate_ui()
        self.playlist_manager_panel.retranslate_ui()

    def _on_library_folders_changed(self, folders: list):
        self._library_folders = folders
        self._rebuild_library_index()
        self._schedule_save()

    def _on_search_text_changed(self, text: str):
        query = text.strip().lower()
        if not query:
            self.search_popup.hide()
            return
        self._populate_search_results(query)
        if self.search_popup.count() > 0:
            self.search_popup.show_below(self.search_field)
        else:
            self.search_popup.hide()

    def _populate_search_results(self, query: str, limit_per_section: int = 8):
        self.search_popup.clear()
        unique_tracks = self._all_known_tracks_deduped()

        # ── Pistes ──────────────────────────────────────────────────
        track_matches = [
            t for t in unique_tracks
            if query in (t.title or "").lower()
            or query in (t.artist or "").lower()
            or query in (t.album or "").lower()
        ][:limit_per_section]

        if track_matches:
            self.search_popup.add_header("Pistes")
            for t in track_matches:
                icon = self._get_track_cover_icon(t)
                self.search_popup.add_result(
                    t.title or os.path.basename(t.path), t.artist, icon,
                    {"type": "track", "track": t},
                )

        # ── Albums ──────────────────────────────────────────────────
        albums = {}
        for t in unique_tracks:
            if t.album and query in t.album.lower():
                albums.setdefault(t.album, []).append(t)
        if albums:
            self.search_popup.add_header("Albums")
            for name, tracks in list(albums.items())[:limit_per_section]:
                icon = self._get_track_cover_icon(tracks[0])
                self.search_popup.add_result(
                    name, tracks[0].artist, icon,
                    {"type": "album", "tracks": tracks},
                )

        # ── Artistes ────────────────────────────────────────────────
        artists = {}
        for t in unique_tracks:
            if t.artist and query in t.artist.lower():
                artists.setdefault(t.artist, []).append(t)
        if artists:
            self.search_popup.add_header("Artistes")
            for name, tracks in list(artists.items())[:limit_per_section]:
                icon = self._get_track_cover_icon(tracks[0])
                self.search_popup.add_result(
                    name, f"{len(tracks)} piste{'s' if len(tracks) > 1 else ''}", icon,
                    {"type": "artist", "tracks": tracks},
                )

        # ── Playlists personnalisées ────────────────────────────────
        playlist_matches = [
            p for p in self.playlist_manager.get_all_playlists()
            if query in (p.name or "").lower()
        ][:limit_per_section]
        if playlist_matches:
            self.search_popup.add_header("Playlists")
            for p in playlist_matches:
                icon = self.playlist_manager_panel._cover_icon(p)
                n = len(p.tracks)
                self.search_popup.add_result(
                    p.name, f"{n} piste{'s' if n > 1 else ''}", icon,
                    {"type": "playlist", "id": p.id},
                )

    def _on_search_result_activated(self, payload: dict):
        kind = payload.get("type")
        if kind == "track":
            self._play_track_now(payload["track"])
        elif kind in ("album", "artist"):
            self._load_custom_tracks_into_playlist(payload["tracks"], mode="replace")
        elif kind == "playlist":
            self._tabs.setCurrentIndex(self._playlists_tab_index)
            self.playlist_manager_panel.refresh_playlists()
            self.playlist_manager_panel._select_playlist_id(payload["id"])
        self.search_field.clear()

    def _play_track_now(self, track):
        """Ajoute une piste trouvée par la recherche à la liste de lecture et la joue immédiatement."""
        self.playlist.add_track(track)
        self.playlist_widget._add_list_item(track)
        self.playlist_widget._update_count()
        self.playlist_widget.playlist_changed.emit()
        self._load_and_play(track, len(self.playlist.tracks) - 1)

    def eventFilter(self, obj, event):
        if obj is self.search_field:
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.search_popup.hide()
                self.search_field.clear()
                return True
            if event.type() == QEvent.Type.FocusOut:
                self.search_popup.hide()
        return super().eventFilter(obj, event)

    def _on_search_hover_preview(self, payload: dict):
        """
        Survol prolongé (>1,5s) d'un résultat de recherche : joue un court
        extrait en arrière-plan. Le lecteur principal (audio ou vidéo, selon
        ce qui joue) est mis en pause le temps de l'extrait, puis reprend
        automatiquement une fois celui-ci terminé.
        """
        kind = payload.get("type")
        track = None

        if kind == "track":
            track = payload.get("track")
        elif kind in ("album", "artist"):
            tracks = payload.get("tracks") or []
            if tracks:
                track = random.choice(tracks)
        elif kind == "playlist":
            playlist = self.playlist_manager.get_playlist(payload.get("id"))
            if playlist and playlist.tracks:
                track = random.choice(playlist.tracks)

        if not track or not getattr(track, "path", None):
            return
        # Les pistes CD sont lues en flux direct depuis le disque ; un
        # aperçu ponctuel n'est pas géré pour elles (hors périmètre).
        if parse_cd_uri(track.path):
            return

        self._pause_main_for_preview()

        duration = self._preview_player.play_excerpt(track.path)
        self._preview_resume_timer.stop()
        if duration > 0:
            # Petite marge pour ne pas couper la reprise juste avant la fin
            # réelle de l'extrait (latence du flux audio).
            self._preview_resume_timer.start(int(duration * 1000) + 150)
        else:
            # Rien n'a pu être joué (fichier illisible, etc.) : pas la peine
            # de garder le lecteur principal en pause pour rien.
            self._resume_main_after_preview()

    def _on_search_hover_preview_cancelled(self):
        self._preview_resume_timer.stop()
        self._preview_player.stop()
        self._resume_main_after_preview()

    def _pause_main_for_preview(self):
        """Met en pause le lecteur principal (audio ou vidéo) avant un
        extrait de recherche, et mémorise lequel pour le reprendre ensuite."""
        if not self._preview_paused_audio and self.engine.state == AudioEngine.STATE_PLAYING:
            self.engine.pause()
            self._preview_paused_audio = True
        if not self._preview_paused_video and self.video_engine.state == VideoEngine.STATE_PLAYING:
            self.video_engine.pause()
            self._preview_paused_video = True

    def _resume_main_after_preview(self):
        """Reprend le lecteur principal là où il a été mis en pause pour
        l'extrait — uniquement s'il n'a pas été touché entre-temps."""
        self._preview_resume_timer.stop()
        if self._preview_paused_audio:
            self._preview_paused_audio = False
            if self.engine.state == AudioEngine.STATE_PAUSED:
                self.engine.play()
        if self._preview_paused_video:
            self._preview_paused_video = False
            if self.video_engine.state == VideoEngine.STATE_PAUSED:
                self.video_engine.play()

    # ══════════════════════════════════════════════════════════════════
    # Timer UI
    # ══════════════════════════════════════════════════════════════════
    def _setup_timer(self):
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(200)
        self._ui_timer.timeout.connect(self._update_ui_from_engine)
        self._ui_timer.start()

    def _update_ui_from_engine(self):
        if self._seeking:
            return
        pos = self.engine.position_seconds
        dur = self.engine.duration_seconds
        if dur > 0:
            progress = int(pos / dur * 1000)
            self.sld_progress.setValue(progress)
            self.intensity_progress.set_progress(progress)
        self.lbl_pos.setText(format_duration(pos))

    # ══════════════════════════════════════════════════════════════════
    # Callbacks engine
    # ══════════════════════════════════════════════════════════════════
    def _on_position_changed(self, pos: float):
        self._last_position = pos

    def _on_track_ended(self):
        from PyQt6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self, "_advance_to_next",
                                  Qt.ConnectionType.QueuedConnection)

    def _on_engine_error(self, msg: str):
        if self._is_handling_error:
            return
        self._is_handling_error = True
        try:
            track = self._current_track
            path = getattr(track, 'path', None) if track else self._current_media_path
            append_error_log(msg, path, context={"kind": "video" if self._media_mode == 'video' else "audio"})
            self.status_bar.showMessage(f"Erreur lecture : {msg}")
            self._advance_to_next()
        finally:
            self._is_handling_error = False

    @pyqtSlot()
    @pyqtSlot()
    def _advance_to_next(self):
        track = self.playlist.next_track()
        if track:
            self._load_and_play(track, self.playlist.current_index)
        else:
            if self._media_mode == 'video':
                self.video_engine.stop()
                self.video_window.controls.set_playing(False)
            else:
                self.engine.stop()
            self._media_mode = 'audio'
            self._set_play_icon(False)
            self.status_bar.showMessage('Fin de liste')

    def _handle_track_error(self, track, error_message: str):
        self._current_track = track
        path = getattr(track, 'path', None) if track else self._current_media_path
        append_error_log(error_message, path, context={"kind": "audio" if not self._is_video(path or '') else "video"})
        self.status_bar.showMessage(f"Erreur lecture : {error_message}")
        self._advance_to_next()
    # ══════════════════════════════════════════════════════════════════
    # Contrôles de transport
    # ══════════════════════════════════════════════════════════════════
    def _on_play_pause(self):
        if self._media_mode == 'video':
            if self.video_engine.state == VideoEngine.STATE_PLAYING:
                self.video_engine.pause()
                self.video_window.controls.set_playing(False)
                self._set_play_icon(False)
                self.status_bar.showMessage('En pause')
            elif self.video_engine.state == VideoEngine.STATE_PAUSED:
                self.video_engine.play()
                self.video_window.controls.set_playing(True)
                self._set_play_icon(True)
                self.status_bar.showMessage('Lecture')
            else:
                track = self.playlist.current_track
                if track:
                    self._load_and_play_video(track.path)
            return
        if self.engine.state == AudioEngine.STATE_PLAYING:
            self.engine.pause()
            self._set_play_icon(False)
            self.status_bar.showMessage('En pause')
        elif self.engine.state == AudioEngine.STATE_PAUSED:
            self.engine.play()
            self._set_play_icon(True)
        else:
            if not self.playlist.tracks:
                return
            if self.playlist.current_index < 0:
                if self.playlist.play_mode == PlayMode.RANDOM:
                    track = self.playlist.next_track()
                else:
                    track = self.playlist.set_current(0)
            else:
                track = self.playlist.current_track
            if track:
                self._load_and_play(track, self.playlist.current_index)
    def _on_stop(self):
        # Le raccourci Échap est partagé avec la fermeture de la recherche :
        # si le champ de recherche a le focus, Échap ferme juste le menu
        # déroulant au lieu d'arrêter la lecture.
        if self.search_field.hasFocus():
            self.search_popup.hide()
            self.search_field.clear()
            return
        if self._media_mode == 'video':
            self.video_engine.stop()
            self.video_window.controls.set_playing(False)
            self.video_window.controls.sld_progress.setValue(0)
            self._media_mode = 'audio'
        else:
            self.engine.stop()
        self._set_play_icon(False)
        self.sld_progress.setValue(0)
        self.lbl_pos.setText('0:00')
        self.status_bar.showMessage('Arrêté')
    def _on_next(self):
        if self._media_mode == 'video':
            self.video_engine.stop()
        track = self.playlist.next_track()
        if track:
            self._load_and_play(track, self.playlist.current_index)

    def _on_prev(self):
        if self._media_mode == 'video':
            self.video_engine.stop()
        track = self.playlist.prev_track()
        if track:
            self._load_and_play(track, self.playlist.current_index)
    def _on_track_activated(self, index: int):
        track = self.playlist.set_current(index)
        if track:
            self._load_and_play(track, index)

    # ── Playlists personnalisées / humeurs ─────────────────────────────
    def _on_mood_selected(self, mood: str):
        """Génère un mix Flow pour l'humeur choisie et lance la lecture."""
        tracks = self.playlist_manager.generate_flow([mood])
        if not tracks:
            QMessageBox.information(
                self, "Mix indisponible",
                f'Aucune piste trouvée pour l\'humeur "{mood}".\n'
                "Ajoutez des pistes à une playlist personnalisée avec cette humeur "
                "depuis l'onglet \"Mes Playlists\"."
            )
            return
        self._load_custom_tracks_into_playlist(tracks, mode="replace")
        self.status_bar.showMessage(f'Mix "{mood}" généré ({len(tracks)} pistes)')

    def _on_play_favorites(self):
        playlist = self.playlist_manager.get_favorites_playlist()
        if not playlist or not playlist.tracks:
            QMessageBox.information(
                self, "Coups de coeur",
                "Ajoutez des morceaux à vos coups de coeur pour créer cette playlist.",
            )
            return
        self._on_load_custom_playlist(playlist.id, "replace")

    def _on_current_track_favorite(self):
        if self._current_track is not None:
            self._on_favorite_requested(self._current_track.path)

    def _on_favorite_requested(self, path: str):
        normalized_path = os.path.normcase(os.path.abspath(path))
        track = next(
            (
                track for track in self.playlist.tracks
                if os.path.normcase(os.path.abspath(track.path)) == normalized_path
            ),
            self._current_track
            if os.path.normcase(os.path.abspath(
                getattr(self._current_track, "path", "")
            )) == normalized_path else None,
        )
        if track is None:
            QMessageBox.warning(
                self, "Coups de coeur",
                "Impossible de retrouver ce morceau dans la liste de lecture.",
            )
            return

        favorite = not self.playlist_manager.is_track_favorite(path)
        if not self.playlist_manager.set_track_favorite(
            CustomTrack.from_dict(track.to_dict()), favorite
        ):
            QMessageBox.warning(
                self, "Coups de coeur",
                "La modification des coups de coeur n'a pas pu être enregistrée.",
            )
            return
        self._refresh_favorites_ui()
        self.playlist_manager_panel.refresh_playlists()

    def _refresh_favorites_ui(self):
        favorites = self.playlist_manager.get_favorites_playlist()
        favorite_paths = [track.path for track in favorites.tracks] if favorites else []
        if hasattr(self, "playlist_widget"):
            self.playlist_widget.set_favorite_paths(favorite_paths)
        if hasattr(self, "btn_favorite_track"):
            current_path = getattr(self._current_track, "path", "")
            is_favorite = bool(
                current_path and self.playlist_manager.is_track_favorite(current_path)
            )
            self.btn_favorite_track.set_favorite(is_favorite)
            self.btn_favorite_track.setEnabled(bool(current_path))
            self.btn_favorite_track.setToolTip(
                "Retirer des coups de coeur" if is_favorite
                else "Ajouter le morceau aux coups de coeur"
            )
            accent = self._colors.get("accent", DEFAULT_COLORS["accent"])
            self.btn_favorite_track.set_accent(accent)

    def _on_tab_changed(self, index: int):
        if index == 0:
            self._refresh_favorites_ui()
        self._schedule_save()

    def _on_open_playlist_manager(self):
        """Bascule vers l'onglet \"Mes Playlists\"."""
        self._tabs.setCurrentIndex(self._playlists_tab_index)

    def _on_load_custom_playlist(self, playlist_id: str, action: str):
        """Charge (remplace) ou ajoute une playlist personnalisée à la liste de lecture."""
        playlist = self.playlist_manager.get_playlist(playlist_id)
        if not playlist or not playlist.tracks:
            return
        self._load_custom_tracks_into_playlist(list(playlist.tracks), mode=action)
        self._tabs.setCurrentIndex(0)
        self.status_bar.showMessage(f'Playlist "{playlist.name}" chargée')

    def _on_load_custom_folder(self, folder_id: str, scope: str):
        """Charge toutes les playlists d'un dossier dans la liste principale."""
        folder_ids = {folder_id}
        if scope == "recursive":
            changed = True
            while changed:
                changed = False
                for folder in self.playlist_manager.get_all_folders():
                    parent_id = getattr(folder, "parent_id", None)
                    if parent_id in folder_ids and folder.id not in folder_ids:
                        folder_ids.add(folder.id)
                        changed = True

        playlists = [
            playlist for playlist in self.playlist_manager.get_all_playlists()
            if playlist.folder_id in folder_ids and playlist.tracks
        ]
        playlists.sort(key=lambda playlist: (playlist.folder_id, playlist.order))
        tracks = [track for playlist in playlists for track in playlist.tracks]
        if not tracks:
            return

        self._load_custom_tracks_into_playlist(tracks, mode="replace")
        self._tabs.setCurrentIndex(0)
        folder = self.playlist_manager.get_folder(folder_id)
        folder_name = folder.name if folder else "Dossier"
        self.status_bar.showMessage(
            f'Dossier "{folder_name}" chargé ({len(playlists)} playlists, '
            f'{len(tracks)} pistes)'
        )

    def _load_custom_tracks_into_playlist(self, tracks, mode: str):
        """Remplace ou ajoute des CustomTrack à la liste de lecture principale."""
        if mode == "replace":
            self.playlist.clear()
            self.playlist_widget.list_widget.clear()
        for track in tracks:
            self.playlist.add_track(track)
            self.playlist_widget._add_list_item(track)
        self.playlist_widget._update_count()
        self.playlist_widget.playlist_changed.emit()
        if mode == "replace" and self.playlist.tracks:
            if self.playlist.play_mode == PlayMode.RANDOM:
                first_track = self.playlist.next_track()
            else:
                first_track = self.playlist.set_current(0)
            if first_track:
                self._load_and_play(first_track, self.playlist.current_index)

    def _is_video(self, path: str) -> bool:
        return any(path.lower().endswith(ext) for ext in SUPPORTED_VIDEO_FORMATS)

    def _load_and_play(self, track, index: int):
        self._current_track = track
        self._current_media_path = track.path
        self.status_bar.showMessage(f"Chargement : {track.title}...")
        if self._is_video(track.path):
            # Arrêter l'audio si actif
            if self.engine.state != 'stopped':
                self.engine.stop()
            self._load_and_play_video(track.path)
            self._update_track_display(track)
            self.playlist_widget.set_active_row(index)
            self._schedule_save()
            return

        # Audio normal
        if self.video_engine.state != 'stopped':
            self.video_engine.stop()
        ok = self.engine.load(track.path)
        if ok:
            is_cd = parse_cd_uri(track.path) is not None
            self._update_progress_stack_for_track(is_cd)
            if not is_cd:
                self.intensity_progress.set_levels(self.engine.get_timeline_levels(240))
            self.engine.play()
            self._set_play_icon(True)
            self._update_track_display(track)
            self.playlist_widget.set_active_row(index)
            dur = self.engine.duration_seconds
            self.lbl_dur.setText(format_duration(dur))
            self.status_bar.showMessage(f"Lecture : {track.title}")
            self._schedule_save()
        else:
            self._on_engine_error("Impossible de charger ou lire le fichier audio")

    def _load_and_play_video(self, path: str):
        """Lance la lecture vidéo et bascule sur l'onglet vidéo."""
        self._media_mode = 'video'
        self._current_track = None
        self._current_media_path = path
        ok = self.video_engine.load(path)
        if ok:
            # Attacher le renderer (la surface doit être visible)
            self.video_engine.play()
            self.video_window.notify_playing()
            # Basculer sur l'onglet vidéo
            for i in range(self._tabs.count()):
                if 'Vidéo' in self._tabs.tabText(i):
                    self._tabs.setCurrentIndex(i)
                    break
            self.status_bar.showMessage(f"Vidéo : {os.path.basename(path)}")
        else:
            self._on_engine_error(f"Impossible de lire la vidéo : {path}")

    def _update_track_display(self, track):
        title = track.title or os.path.basename(track.path)
        self.lbl_title.setText(title)
        self.lbl_artist.setText(track.artist or "Artiste inconnu")
        self.lbl_album.setText(track.album or "")
        self._set_track_artwork(track)
        self.setWindowTitle(f"{title} — SolarSound")
        self._update_next_track_panel()
        self._refresh_favorites_ui()

    def _set_track_artwork(self, track):
        self.art_label.setText("")
        self.art_label.setStyleSheet("border: none; background: transparent;")
        self.art_label.setPixmap(self._default_cover_pixmap(self.art_frame.size()))

        if not track or not getattr(track, "path", None):
            return

        cover_data = read_cover_art_data(track.path)
        if not cover_data:
            # Les pistes CD n'ont pas de fichier réel (donc pas de tags à
            # lire) : on retombe sur la pochette récupérée en ligne pour
            # ce lecteur, si elle a été trouvée (voir CdMetadataWorker).
            cd_location = parse_cd_uri(track.path)
            if cd_location:
                drive, _ = cd_location
                cover_data = get_cached_cover_for_drive(drive)
        if not cover_data:
            return

        pixmap = QPixmap()
        if not pixmap.loadFromData(cover_data):
            return

        scaled = pixmap.scaled(
            self.art_frame.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.art_label.setPixmap(scaled)
        self.art_label.setText("")
        self.art_label.setStyleSheet("border: none; background: transparent;")

    # ══════════════════════════════════════════════════════════════════
    # Volume & Seek
    # ══════════════════════════════════════════════════════════════════
    def _on_volume_changed(self, value: int):
        vol = slider_to_gain(value)
        self.engine.set_volume(vol)
        self.video_engine.set_volume(value)
        self.lbl_vol_val.setText(f"{int(round(vol * 100))}%")
        self._schedule_save()

    def _on_seek_start(self):
        self._seeking = True

    def _on_seek_end(self):
        self._seek_to_progress(self.sld_progress.value())
        self._seeking = False

    def _on_intensity_seek(self, value: int):
        self.sld_progress.setValue(value)
        self.intensity_progress.set_progress(value)
        self._seeking = True
        self._seek_to_progress(value)

    def _on_intensity_seek_end(self):
        self._seeking = False

    def _on_progress_dragged(self, value: int):
        if self._seeking:
            self._seek_to_progress(value)

    def _seek_to_progress(self, value: int):
        self.engine.seek(value / 1000.0 * self.engine.duration_seconds)

    def _set_progress_style(self, style: str, emit: bool = True):
        self._progress_style = style if style in ("classic", "intensity", "intensity_centered") else "classic"
        self.settings_panel.audio_tab.cmb_progress.blockSignals(True)
        self.settings_panel.audio_tab.cmb_progress.setCurrentIndex(
            self.settings_panel.audio_tab.cmb_progress.findData(self._progress_style)
        )
        self.settings_panel.audio_tab.cmb_progress.blockSignals(False)

        # Les CD audio sont lus directement depuis le disque, sans être
        # chargés en mémoire : impossible d'y calculer une intensité par
        # segment, donc la barre classique reste forcée tant qu'un CD est
        # en cours de lecture, quel que soit le style choisi ici (qui
        # s'appliquera normalement à la prochaine piste non-CD).
        current_is_cd = bool(
            self._current_track and parse_cd_uri(getattr(self._current_track, "path", "") or "")
        )
        self._update_progress_stack_for_track(current_is_cd)
        self.intensity_progress.set_theme_colors(self._colors)
        if emit:
            self._schedule_save()

    def _update_progress_stack_for_track(self, is_cd: bool):
        """
        Bascule la barre de progression : classique (linéaire) pour les CD
        audio — lus en flux direct depuis le disque, jamais chargés
        entièrement en mémoire, donc sans intensité calculable — et la
        barre choisie par l'utilisateur (classique ou intensité) pour les
        autres sources, qui elles sont chargées en mémoire.
        """
        if is_cd:
            self.progress_stack.setCurrentWidget(self.sld_progress)
        else:
            self.progress_stack.setCurrentWidget(
                self.intensity_progress if self._progress_style != "classic" else self.sld_progress
            )
            self.intensity_progress.set_variant(self._progress_style == "intensity_centered")

    def _on_progress_style_changed(self, style: str):
        self._set_progress_style(style)

    # ══════════════════════════════════════════════════════════════════
    # Mode de lecture
    # ══════════════════════════════════════════════════════════════════
    def _on_order_toggle(self):
        if self._order_mode == PlayMode.SEQUENTIAL:
            self._order_mode = PlayMode.RANDOM
            self._sequential_loop_active = False
        else:
            self._order_mode = PlayMode.SEQUENTIAL
            self._sequential_loop_active = False
        self._apply_play_mode()

    def _on_loop_toggle(self):
        if self._loop_pref == PlayMode.LOOP_ALL:
            self._loop_pref = PlayMode.LOOP_ONE
            self._sequential_loop_active = True
        elif self._loop_pref == PlayMode.LOOP_ONE:
            self._loop_pref = PlayMode.LOOP_ALL
            self._sequential_loop_active = False
        else:
            self._loop_pref = PlayMode.LOOP_ALL
            self._sequential_loop_active = True

        self._apply_play_mode()

    def _apply_play_mode(self):
        if self._order_mode == PlayMode.RANDOM:
            mode = PlayMode.RANDOM
        elif self._sequential_loop_active:
            mode = self._loop_pref
        else:
            mode = PlayMode.SEQUENTIAL

        self.playlist.play_mode = mode
        if mode == PlayMode.RANDOM and self.playlist.current_index >= 0:
            self.playlist.set_current(self.playlist.current_index)
        self._update_mode_buttons()

        _LABELS = {PlayMode.SEQUENTIAL: 'SEQUENTIEL', PlayMode.LOOP_ALL: 'BOUCLE ALL',
                   PlayMode.LOOP_ONE: 'BOUCLE 1', PlayMode.RANDOM: 'ALEATOIRE'}
        self.lbl_mode_indicator.setText('\u26ab ' + _LABELS[mode])
        self._update_next_track_panel()
        self._schedule_save()

    def _update_mode_buttons(self):
        accent = self._colors.get("accent", DEFAULT_COLORS["accent"])
        if self._order_mode == PlayMode.RANDOM:
            self.btn_order.setIcon(self._tinted_icon('aleatoire.svg', accent))
            self.btn_order.setToolTip('Lecture aléatoire')
        else:
            self.btn_order.setIcon(self._tinted_icon('sequential.svg', accent))
            self.btn_order.setToolTip('Lecture séquentielle')

        if not self._sequential_loop_active:
            self.btn_loop.setIcon(self._tinted_icon('sequential.svg', accent))
            self.btn_loop.setToolTip('Boucle désactivée')
        elif self._loop_pref == PlayMode.LOOP_ALL:
            self.btn_loop.setIcon(self._tinted_icon('boucle.svg', accent))
            self.btn_loop.setToolTip('Boucle sur toute la liste')
        else:
            self.btn_loop.setIcon(self._tinted_icon('oneboucle.svg', accent))
            self.btn_loop.setToolTip('Boucle sur le morceau actuel')

    def _set_play_mode(self, mode: PlayMode):
        if mode == PlayMode.RANDOM:
            self._order_mode = PlayMode.RANDOM
            self._sequential_loop_active = False
        elif mode == PlayMode.SEQUENTIAL:
            self._order_mode = PlayMode.SEQUENTIAL
            self._sequential_loop_active = False
            self._loop_pref = PlayMode.LOOP_ALL
        else:
            self._order_mode = PlayMode.SEQUENTIAL
            self._loop_pref = mode
            self._sequential_loop_active = True
        self._apply_play_mode()

    # ══════════════════════════════════════════════════════════════════
    # Spatialisation
    # ══════════════════════════════════════════════════════════════════
    def _on_shortcuts_changed(self, shortcuts: dict):
        self._shortcuts = shortcuts
        self._apply_shortcuts()
        self._schedule_save()

    def _on_startup_changed(self, config: dict):
        self._startup_config = {
            "enabled": bool(config.get("enabled", False)),
            "mode": config.get("mode", "none"),
            "value": config.get("value", ""),
        }
        if not set_launch_at_startup(self._startup_config["enabled"]):
            self.status_bar.showMessage(
                "Le démarrage automatique est disponible uniquement sous Windows."
            )
        self._schedule_save()

    def start_configured_playback(self):
        """Lance le contenu choisi dans les options de démarrage Windows."""
        config = self._startup_config
        if not config.get("enabled"):
            return

        mode = config.get("mode", "none")
        value = config.get("value", "")
        if mode == "mood":
            tracks = self.playlist_manager.generate_flow([value]) if value else []
            if tracks:
                self._load_custom_tracks_into_playlist(tracks, mode="replace")
            return

        if mode == "playlist":
            playlist = self.playlist_manager.get_playlist(value)
            tracks = playlist.tracks if playlist else []
            if tracks:
                self._load_custom_tracks_into_playlist(list(tracks), mode="replace")
            return

        if mode == "playlist_folder":
            tracks = []
            for playlist in self.playlist_manager.get_all_playlists():
                if playlist.folder_id == value:
                    tracks.extend(playlist.tracks)
            if tracks:
                self._load_custom_tracks_into_playlist(tracks, mode="replace")
            return

        if mode == "filesystem_folder" and os.path.isdir(value):
            paths = []
            for root, _, files in os.walk(value):
                for filename in sorted(files):
                    path = os.path.join(root, filename)
                    if os.path.splitext(filename)[1].lower() in Playlist.ALL_FORMATS:
                        paths.append(path)
            if paths:
                self._open_files_from_args(paths)

    def _on_colors_changed(self, colors: dict):
        self._colors = colors
        ss = build_stylesheet(colors, self._font_cfg)
        self.setStyleSheet(ss)
        self._resync_local_styles(colors)
        self.visualizer.set_theme_colors(colors)
        self.intensity_progress.set_theme_colors(colors)
        self._refresh_transport_icons()
        self.equalizer_panel.set_theme_colors(colors)
        self.spatial_panel.set_theme_colors(colors)
        self.rotation_panel.set_theme_colors(colors)
        if self.vinyl_panel is not None:
            self.vinyl_panel.set_theme_colors(colors)
        self.playlist_widget.set_theme_colors(colors)
        self.search_popup.set_accent_color(colors.get("accent", "#f5a623"))
        self.video_window.controls.set_theme_colors(colors)
        self._schedule_save()

    def _on_font_changed(self, font_cfg: dict):
        self._font_cfg = font_cfg
        ss = build_stylesheet(self._colors, font_cfg)
        self.setStyleSheet(ss)
        self._schedule_save()

    def _on_output_changed(self, device_id):
        self.engine.output_device = device_id
        if self.engine.state == self.engine.STATE_PLAYING:
            self.engine._start_stream()
        self._schedule_save()

    def _apply_shortcuts(self):
        """Reapplique les raccourcis clavier depuis self._shortcuts."""
        from PyQt6.QtGui import QKeySequence
        sc = self._shortcuts
        # Toutes les commandes passent par des actions globales : cela évite
        # que le focus d'un champ ou d'un onglet fasse perdre les raccourcis.
        mapping = {
            'play_pause': self._on_play_pause,
            'stop': self._on_stop,
            'next': self._on_next,
            'prev': self._on_prev,
            'seek_fwd_5': lambda _checked=False: self._seek_by(5),
            'seek_bwd_5': lambda _checked=False: self._seek_by(-5),
            'seek_fwd_60': lambda _checked=False: self._seek_by(60),
            'seek_bwd_60': lambda _checked=False: self._seek_by(-60),
            'volume_up': lambda _checked=False: self._change_volume(5),
            'volume_down': lambda _checked=False: self._change_volume(-5),
            'mute': self._toggle_mute,
            'fullscreen': self._toggle_video_fullscreen,
            'next_frame': self._next_video_frame,
            'prev_frame': self._prev_video_frame,
            'speed_up': lambda _checked=False: self._change_video_speed(0.25),
            'speed_down': lambda _checked=False: self._change_video_speed(-0.25),
            'speed_reset': lambda _checked=False: self._set_video_speed(1.0),
            'open_file': self.playlist_widget._on_add_files,
            'open_cd': self.playlist_widget._on_add_cd,
            'scan_missing': self.playlist_manager_panel._on_scan_library,
            'close': self.close,
        }
        shortcut_actions = getattr(self, "_shortcut_actions", {})
        tab_targets = {
            "tab_equalizer": self.equalizer_panel,
            "tab_my_playlists": self.playlist_manager_panel,
            "tab_playlist": self.playlist_widget,
            "tab_video": self.video_window,
            "tab_surround": self.spatial_panel,
            "tab_rotation": self.rotation_panel,
            "tab_vinyl": self.vinyl_panel,
            "tab_settings": self.settings_panel,
        }
        mapping.update({
            key: (lambda _checked=False, target=target: self._activate_tab(target))
            for key, target in tab_targets.items() if target is not None
        })
        for key, callback in mapping.items():
            if key not in sc or callback is None:
                continue
            action = shortcut_actions.get(key)
            if action is None:
                action = QAction(self)
                action.triggered.connect(callback)
                shortcut_actions[key] = action
                self.addAction(action)
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            action.setShortcut(QKeySequence(sc[key]))
        self._shortcut_actions = shortcut_actions
        self._shortcut_map = sc

    def _seek_by(self, seconds):
        if self._media_mode == 'video':
            self.video_engine.seek(max(0, self.video_engine.position_seconds + seconds))
        else:
            self.engine.seek(max(0, self.engine.position_seconds + seconds))

    def _change_volume(self, delta):
        self.sld_volume.setValue(max(50, min(SLIDER_MAX, self.sld_volume.value() + delta)))

    def _toggle_mute(self):
        if self.sld_volume.value() > 50:
            self._volume_before_mute = self.sld_volume.value()
            self.sld_volume.setValue(50)
        else:
            self.sld_volume.setValue(getattr(self, '_volume_before_mute', 100))

    def _toggle_video_fullscreen(self):
        if self._media_mode == 'video':
            self.video_window._toggle_fullscreen()

    def _next_video_frame(self):
        if self._media_mode == 'video':
            self.video_engine.step_forward()

    def _prev_video_frame(self):
        if self._media_mode == 'video':
            self.video_engine.step_backward()

    def _change_video_speed(self, delta):
        if self._media_mode == 'video':
            speed = max(0.25, min(10.0, self.video_engine.config.speed + delta))
            self._set_video_speed(speed)

    def _set_video_speed(self, speed):
        if self._media_mode == 'video':
            self.video_engine.set_speed(speed)
            self.video_window.controls.set_speed(speed)

    def _activate_tab(self, widget):
        index = self._tabs.indexOf(widget)
        if index >= 0:
            self._tabs.setCurrentIndex(index)

    def _on_spatial_config_changed(self, config):
        self.engine.config = config
        self.engine.update_lpf()
        active = []
        if config.double_front_to_surround:
            active.append("Surround")
        if config.mix_to_lfe:
            active.append("LFE")
        mode = " + ".join(active) if active else "STÉRÉO"
        self.lbl_mode_indicator.setText(f"⬤ {mode.upper()}")
        self._schedule_save()

    def _on_equalizer_config_changed(self, config):
        self.engine.equalizer_config.__dict__.update(config)
        self._schedule_save()

    def _on_visualizer_toggled(self, checked: bool):
        if self.visualizer.is_animation_enabled() != checked:
            self.visualizer.set_enabled_animation(checked, emit=False)
        self._schedule_save()

    def _on_vinyl_config_changed(self, config):
        if self.engine.vinyl:
            self.engine.vinyl.config = config
        self._schedule_save()

    def _on_video_ended(self):
        from PyQt6.QtCore import QMetaObject
        QMetaObject.invokeMethod(self, '_advance_to_next',
                                  Qt.ConnectionType.QueuedConnection)
    def _on_playlist_changed(self):
        self._update_next_track_panel()
        self._schedule_save()

    def _on_restored_track_metadata(self, track):
        if self._current_track is track:
            self._update_track_display(track)

    # ══════════════════════════════════════════════════════════════════
    # Clavier global
    # ══════════════════════════════════════════════════════════════════
    def keyPressEvent(self, event):
        try:
            from PyQt6.QtGui import QKeySequence
            combo = QKeySequence(event.modifiers() | event.key()).toString()
        except Exception:
            super().keyPressEvent(event)
            return

        sc = getattr(self, '_shortcut_map', self._shortcuts)

        if combo == sc.get('play_pause', 'Space'):
            self._on_play_pause()
        elif combo == sc.get('stop', 'Escape'):
            self._on_stop()
        elif combo == sc.get('next', 'Right'):
            self._on_next()
        elif combo == sc.get('prev', 'Left'):
            self._on_prev()
        elif combo == sc.get('next_frame', 'Period') and self._media_mode == 'video':
            self.video_engine.step_forward()
        elif combo == sc.get('prev_frame', 'Comma') and self._media_mode == 'video':
            self.video_engine.step_backward()
        elif combo == sc.get('speed_up', 'Ctrl+Up'):
            spd = min(10.0, (self.video_engine.config.speed if self._media_mode == 'video'
                             else 1.0) + 0.25)
            if self._media_mode == 'video':
                self.video_engine.set_speed(spd)
                self.video_window.controls.set_speed(spd)
        elif combo == sc.get('speed_down', 'Ctrl+Down'):
            spd = max(0.25, (self.video_engine.config.speed if self._media_mode == 'video'
                              else 1.0) - 0.25)
            if self._media_mode == 'video':
                self.video_engine.set_speed(spd)
                self.video_window.controls.set_speed(spd)
        elif combo == sc.get('speed_reset', 'Ctrl+0'):
            if self._media_mode == 'video':
                self.video_engine.set_speed(1.0)
                self.video_window.controls.set_speed(1.0)
        elif combo == sc.get('volume_up', 'Up'):
            self.sld_volume.setValue(min(SLIDER_MAX, self.sld_volume.value() + 5))
        elif combo == sc.get('volume_down', 'Down'):
            self.sld_volume.setValue(max(50, self.sld_volume.value() - 5))
        elif combo == sc.get('seek_fwd_5', 'Ctrl+Right'):
            if self._media_mode == 'video':
                self.video_engine.seek(self.video_engine.position_seconds + 5)
            else:
                self.engine.seek(self.engine.position_seconds + 5)
        elif combo == sc.get('seek_bwd_5', 'Ctrl+Left'):
            if self._media_mode == 'video':
                self.video_engine.seek(max(0, self.video_engine.position_seconds - 5))
            else:
                self.engine.seek(max(0, self.engine.position_seconds - 5))
        else:
            super().keyPressEvent(event)

    # ══════════════════════════════════════════════════════════════════
    # Divers
    # ══════════════════════════════════════════════════════════════════
    def _show_about(self):
        QMessageBox.about(self, "SolarSound",
            "<h2 style='color:#f5a623'>SolarSound</h2>"
            "<p>Lecteur de musique avec spatialisation 5.1</p>"
            "<ul>"
            "<li>Formats : MP3, WAV</li>"
            "<li>Spatialisation 5.1 (FL, FR, C, LFE, SL, SR)</li>"
            "<li>Doublement façade → surround</li>"
            "<li>Mixage mono → caisson de basse (passe-bas)</li>"
            "<li>Listes de lecture .playlist</li>"
            "<li>Modes : séquentiel, boucle 1, boucle all, aléatoire</li>"
            "</ul>"
        )

    def closeEvent(self, event):
        self.engine.stop()
        self.video_engine.release()
        self._save_session()
        event.accept()
