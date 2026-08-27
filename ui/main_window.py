"""Fenêtre principale SolarSound"""

import os
import sys
from typing import List

from PyQt6.QtWidgets import (
    QTabBar,
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QTabWidget, QFrame,
    QSizePolicy, QMenuBar, QStatusBar, QMessageBox,
    QFileDialog, QGroupBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence, QPixmap

try:
    from .settings_panel import SettingsPanel, build_stylesheet, DEFAULT_SHORTCUTS, DEFAULT_COLORS, DEFAULT_FONT
    from .video_window import VideoWindow
    from ..video.player import VideoEngine, SUPPORTED_VIDEO_FORMATS
    from .theme import STYLESHEET
    from .playlist_widget import PlaylistWidget
    from .spatial_panel import SpatialPanel
    from .rotation_panel import RotationPanel
    from .vinyl_panel import VinylPanel
    from .equalizer_panel import EqualizerPanel
    from .visualizer_widget import SolarVisualizer, N_BANDS as VIZ_N_BANDS
    from ..core.playlist import Playlist, PlayMode, Track
    from ..core.session import SessionManager, SessionState, WindowState
    from ..audio.engine import AudioEngine, SpatialConfig
    from ..audio.cd import parse_cd_uri
    from ..audio.metadata import format_duration, read_metadata, read_cover_art_data
    from ..core.error_logging import append_error_log
    from ..core.volume import gain_to_slider_value, slider_to_gain
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
    from ui.playlist_widget import PlaylistWidget
    from ui.spatial_panel import SpatialPanel
    from ui.rotation_panel import RotationPanel
    from ui.vinyl_panel import VinylPanel
    from ui.visualizer_widget import SolarVisualizer, N_BANDS as VIZ_N_BANDS
    from core.playlist import Playlist, PlayMode, Track
    from core.session import SessionManager, SessionState, WindowState
    from audio.engine import AudioEngine, SpatialConfig
    from ui.equalizer_panel import EqualizerPanel
    from audio.cd import parse_cd_uri
    from audio.metadata import format_duration, read_metadata, read_cover_art_data
    from core.error_logging import append_error_log
    from core.volume import gain_to_slider_value, slider_to_gain


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


class MainWindow(QMainWindow):
    def __init__(self, open_files: List[str] = None):
        super().__init__()
        self.playlist = Playlist()
        self.engine = AudioEngine()
        self._current_track = None
        self._current_media_path = None
        self._is_handling_error = False
        self.engine.on_position_changed = self._on_position_changed
        self.engine.on_track_ended = self._on_track_ended
        self.engine.on_error = self._on_engine_error

        self._seeking = False
        self._last_position = 0.0
        self._session = SessionManager()

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

        # Mode courant : 'audio' ou 'video'
        self._media_mode = 'audio'

        self.setWindowTitle("SolarSound")
        self.setWindowIcon(QIcon(self._icon_path("solarsound.ico")))
        self.setMinimumSize(900, 680)
        self.setStyleSheet(STYLESHEET)

        self._build_ui()
        # Autoriser le glisser-déposer sur la fenêtre principale
        self.setAcceptDrops(True)
        self._build_menu()
        self._build_status_bar()
        self._setup_timer()

        # Restaurer la session
        session = self._session.load()
        self._restore_session(session)

        # Fichiers ouverts via "Lire avec" ou argument CLI
        if open_files:
            self._open_files_from_args(open_files)

    # ── Glisser-déposer global (redirige vers _open_files_from_args) ──
    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()
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
                        if any(ext.endswith(e) for e in self.playlist.ALL_FORMATS):
                            paths.append(os.path.join(root, f))
            else:
                paths.append(local)

        if paths:
            self._open_files_from_args(paths)

    def _icon_path(self, name):
        return os.path.join(self._icons_dir, name)

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
            play_mode=self.playlist.play_mode.name,
            volume=self.sld_volume.value(),
            spatial_config=spatial,
            equalizer_config=equalizer,
        )
        state.vinyl_config = vinyl_cfg
        state.visualizer_enabled = self.visualizer.is_animation_enabled()
        state.shortcuts = self._shortcuts
        state.colors    = self._colors
        state.font_cfg  = self._font_cfg
        self._session.save(state)

    def _restore_session(self, state: SessionState):
        """Restaure la fenêtre, la playlist et les paramètres."""
        # ── Fenêtre & écran ──────────────────────────────────────────
        self._restore_window_geometry(state.window)

        # ── Volume ───────────────────────────────────────────────────
        saved_value = state.volume
        slider_value = max(50, min(150, saved_value))
        self.sld_volume.setValue(slider_value)

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
                self.playlist_widget._add_files(valid_paths)
                idx = min(state.current_index, len(self.playlist.tracks) - 1)
                self.playlist.set_current(idx)
                self.playlist_widget.set_active_row(idx)

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
        root.addWidget(self._tabs, stretch=1)

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        lbl_title = QLabel("SOLAR")
        lbl_title.setObjectName("title_label")
        lbl_title.setStyleSheet(
            "font-size: 26px; font-weight: 900; color: #f5a623; letter-spacing: 4px;"
        )

        lbl_sound = QLabel("SOUND")
        lbl_sound.setStyleSheet(
            "font-size: 26px; font-weight: 300; color: #e8d5a0; letter-spacing: 4px;"
        )

        lbl_sub = QLabel("LECTEUR 5.1")
        lbl_sub.setStyleSheet(
            "font-size: 10px; color: #5a4a28; letter-spacing: 6px; margin-left: 4px;"
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
        self.lbl_title.setStyleSheet(
            "font-size: 17px; font-weight: bold; color: #f5c842;"
        )
        self.lbl_title.setWordWrap(False)
        info_col.addWidget(self.lbl_title)

        self.lbl_artist = QLabel("—")
        self.lbl_artist.setObjectName("track_artist")
        self.lbl_artist.setStyleSheet("font-size: 13px; color: #a08060;")
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
        self.sld_volume.setRange(50, 150)
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

        self.sld_progress = QSlider(Qt.Orientation.Horizontal)
        self.sld_progress.setRange(0, 1000)
        self.sld_progress.setValue(0)
        self.sld_progress.sliderPressed.connect(self._on_seek_start)
        self.sld_progress.sliderReleased.connect(self._on_seek_end)
        layout.addWidget(self.sld_progress, stretch=1)

        self.lbl_dur = QLabel("0:00")
        self.lbl_dur.setObjectName("time_label")
        self.lbl_dur.setFixedWidth(45)
        self.lbl_dur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_dur.setStyleSheet("font-family: 'Consolas', monospace; color: #7a6840;")
        layout.addWidget(self.lbl_dur)

        return layout

    def _build_transport(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(4)

        self.btn_order = QPushButton()
        self.btn_order.setIcon(QIcon(self._icon_path("sequential.svg")))
        self.btn_order.setIconSize(QSize(18, 18))
        self.btn_order.setToolTip("Lecture séquentielle")
        self.btn_order.setCheckable(False)
        self.btn_order.setFixedSize(32, 32)

        self.btn_loop = QPushButton()
        self.btn_loop.setIcon(QIcon(self._icon_path("boucle.svg")))
        self.btn_loop.setIconSize(QSize(18, 18))
        self.btn_loop.setToolTip("Boucle sur toute la liste")
        self.btn_loop.setCheckable(False)
        self.btn_loop.setFixedSize(32, 32)

        self._order_mode = PlayMode.SEQUENTIAL
        self._loop_pref = PlayMode.LOOP_ALL
        self._sequential_loop_active = False

        mode_layout.addWidget(self.btn_loop)
        mode_layout.addWidget(self.btn_order)

        self.btn_order.clicked.connect(self._on_order_toggle)
        self.btn_loop.clicked.connect(self._on_loop_toggle)

        layout.addLayout(mode_layout)
        layout.addSpacing(24)

        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(QIcon(self._icon_path("preview.svg")))
        self.btn_prev.setIconSize(QSize(24, 24))
        self.btn_prev.setObjectName("btn_prev")
        self.btn_prev.setToolTip("Morceau précédent")
        self.btn_prev.clicked.connect(self._on_prev)
        layout.addWidget(self.btn_prev)

        layout.addSpacing(8)

        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(QIcon(self._icon_path("stop.svg")))
        self.btn_stop.setIconSize(QSize(24, 24))
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setToolTip("Stop")
        self.btn_stop.clicked.connect(self._on_stop)
        layout.addWidget(self.btn_stop)

        layout.addSpacing(8)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(QIcon(self._icon_path("play.svg")))
        self.btn_play.setIconSize(QSize(24, 24))
        self.btn_play.setObjectName("btn_play")
        self.btn_play.setToolTip("Lecture / Pause")
        self.btn_play.clicked.connect(self._on_play_pause)
        layout.addWidget(self.btn_play)

        layout.addSpacing(8)

        self.btn_next = QPushButton()
        self.btn_next.setIcon(QIcon(self._icon_path("next.svg")))
        self.btn_next.setIconSize(QSize(24, 24))
        self.btn_next.setObjectName("btn_next")
        self.btn_next.setToolTip("Morceau suivant")
        self.btn_next.clicked.connect(self._on_next)
        layout.addWidget(self.btn_next)

        return layout

    def _build_tabs(self) -> DetachableTabWidget:
        tabs = DetachableTabWidget()

        # ── Playlist ──────────────────────────────────────────────────
        self.playlist_widget = PlaylistWidget(self.playlist)
        self.playlist_widget.track_activated.connect(self._on_track_activated)
        self.playlist_widget.playlist_changed.connect(self._on_playlist_changed)
        tabs.addTab(self.playlist_widget, "📋  Playlist")

        # ── Lecteur Vidéo (prioritaire, premier onglet clé) ───────────
        self.video_window = VideoWindow(self.video_engine, self._icons_dir)
        self.video_window.request_prev.connect(self._on_prev)
        self.video_window.request_next.connect(self._on_next)
        self.video_window.request_stop.connect(self._on_stop)
        tabs.addTab(self.video_window, "🎬  Vidéo")

        # ── Spatialisation ────────────────────────────────────────────
        self.spatial_panel = SpatialPanel(self.engine.config)
        self.spatial_panel.config_changed.connect(self._on_spatial_config_changed)
        tabs.addTab(self.spatial_panel, "🔊  5.1")

        # ── Egaliseur ────────────────────────────────────────────────
        self.equalizer_panel = EqualizerPanel(self.engine.equalizer_config.__dict__)
        self.equalizer_panel.config_changed.connect(self._on_equalizer_config_changed)
        tabs.addTab(self.equalizer_panel, "〽  Égaliseur")

        # ── Rotation ─────────────────────────────────────────────────
        self.rotation_panel = RotationPanel(self.engine.config)
        self.rotation_panel.config_changed.connect(self._on_spatial_config_changed)
        tabs.addTab(self.rotation_panel, "🌀  Rotation")

        # ── Vinyle ────────────────────────────────────────────────────
        if self.engine.vinyl:
            self.vinyl_panel = VinylPanel(self.engine.vinyl.config)
            self.vinyl_panel.config_changed.connect(self._on_vinyl_config_changed)
            tabs.addTab(self.vinyl_panel, "💿  Vinyle")
        else:
            self.vinyl_panel = None

        # ── Paramètres ────────────────────────────────────────────────
        self.settings_panel = SettingsPanel(
            self._shortcuts, self._colors, self._font_cfg
        )
        self.settings_panel.shortcuts_changed.connect(self._on_shortcuts_changed)
        self.settings_panel.colors_changed.connect(self._on_colors_changed)
        self.settings_panel.font_changed.connect(self._on_font_changed)
        tabs.addTab(self.settings_panel, "⚙  Paramètres")

        # Activer l'onglet vidéo par défaut (index 1)
        tabs.setCurrentIndex(1)

        return tabs
    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("&Fichier")
        act_open = QAction("&Ouvrir des fichiers…", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self.playlist_widget._on_add_files)
        file_menu.addAction(act_open)

        act_open_pl = QAction("Ouvrir une &liste…", self)
        act_open_pl.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_pl.triggered.connect(self.playlist_widget._on_load_playlist)
        file_menu.addAction(act_open_pl)

        act_save_pl = QAction("&Enregistrer la liste…", self)
        act_save_pl.setShortcut(QKeySequence("Ctrl+S"))
        act_save_pl.triggered.connect(self.playlist_widget._on_save_playlist)
        file_menu.addAction(act_save_pl)

        file_menu.addSeparator()
        act_quit = QAction("&Quitter", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        play_menu = mb.addMenu("&Lecture")
        act_pp = QAction("Lecture / &Pause", self)
        act_pp.setShortcut(Qt.Key.Key_Space)
        act_pp.triggered.connect(self._on_play_pause)
        play_menu.addAction(act_pp)

        act_stop = QAction("&Stop", self)
        act_stop.setShortcut(Qt.Key.Key_Escape)
        act_stop.triggered.connect(self._on_stop)
        play_menu.addAction(act_stop)

        act_next = QAction("&Suivant", self)
        act_next.setShortcut(Qt.Key.Key_Right)
        act_next.triggered.connect(self._on_next)
        play_menu.addAction(act_next)

        act_prev = QAction("&Précédent\n", self)
        act_prev.setShortcut(Qt.Key.Key_Left)
        act_prev.triggered.connect(self._on_prev)
        play_menu.addAction(act_prev)

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

    def _build_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Prêt")

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
            self.sld_progress.setValue(int(pos / dur * 1000))
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
            self.btn_play.setIcon(QIcon(self._icon_path('play.svg')))
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
                self.btn_play.setIcon(QIcon(self._icon_path('play.svg')))
                self.status_bar.showMessage('En pause')
            elif self.video_engine.state == VideoEngine.STATE_PAUSED:
                self.video_engine.play()
                self.video_window.controls.set_playing(True)
                self.btn_play.setIcon(QIcon(self._icon_path('pause.svg')))
                self.status_bar.showMessage('Lecture')
            else:
                track = self.playlist.current_track
                if track:
                    self._load_and_play_video(track.path)
            return
        if self.engine.state == AudioEngine.STATE_PLAYING:
            self.engine.pause()
            self.btn_play.setIcon(QIcon(self._icon_path('play.svg')))
            self.status_bar.showMessage('En pause')
        elif self.engine.state == AudioEngine.STATE_PAUSED:
            self.engine.play()
            self.btn_play.setIcon(QIcon(self._icon_path('pause.svg')))
        else:
            if not self.playlist.tracks:
                return
            if self.playlist.current_index < 0:
                self.playlist.set_current(0)
            track = self.playlist.current_track
            if track:
                self._load_and_play(track, self.playlist.current_index)
    def _on_stop(self):
        if self._media_mode == 'video':
            self.video_engine.stop()
            self.video_window.controls.set_playing(False)
            self.video_window.controls.sld_progress.setValue(0)
            self._media_mode = 'audio'
        else:
            self.engine.stop()
        self.btn_play.setIcon(QIcon(self._icon_path('play.svg')))
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
            self.engine.play()
            self.btn_play.setIcon(QIcon(self._icon_path("pause.svg")))
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

    def _set_track_artwork(self, track):
        self.art_label.setText("♪")
        self.art_label.setStyleSheet("font-size: 32px; color: #3d3420; border: none; background: transparent;")
        self.art_label.setPixmap(QPixmap())

        if not track or not getattr(track, "path", None):
            return

        cover_data = read_cover_art_data(track.path)
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
        dur = self.engine.duration_seconds
        pos = self.sld_progress.value() / 1000.0 * dur
        self.engine.seek(pos)
        self._seeking = False

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
        else:
            self._loop_pref = PlayMode.LOOP_ALL

        if self._order_mode == PlayMode.SEQUENTIAL:
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
        self._update_mode_buttons()

        _LABELS = {PlayMode.SEQUENTIAL: 'SEQUENTIEL', PlayMode.LOOP_ALL: 'BOUCLE ALL',
                   PlayMode.LOOP_ONE: 'BOUCLE 1', PlayMode.RANDOM: 'ALEATOIRE'}
        self.lbl_mode_indicator.setText('\u26ab ' + _LABELS[mode])
        self._schedule_save()

    def _update_mode_buttons(self):
        if self._order_mode == PlayMode.RANDOM:
            self.btn_order.setIcon(QIcon(self._icon_path('aleatoire.svg')))
            self.btn_order.setToolTip('Lecture aléatoire')
        else:
            self.btn_order.setIcon(QIcon(self._icon_path('sequential.svg')))
            self.btn_order.setToolTip('Lecture séquentielle')

        if self._loop_pref == PlayMode.LOOP_ALL:
            self.btn_loop.setIcon(QIcon(self._icon_path('boucle.svg')))
            self.btn_loop.setToolTip('Boucle sur toute la liste')
        else:
            self.btn_loop.setIcon(QIcon(self._icon_path('oneboucle.svg')))
            self.btn_loop.setToolTip('Boucle sur le morceau actuel')

    def _set_play_mode(self, mode: PlayMode):
        if mode == PlayMode.RANDOM:
            self._order_mode = PlayMode.RANDOM
            self._sequential_loop_active = False
        elif mode == PlayMode.SEQUENTIAL:
            self._order_mode = PlayMode.SEQUENTIAL
            self._sequential_loop_active = False
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

    def _on_colors_changed(self, colors: dict):
        self._colors = colors
        ss = build_stylesheet(colors, self._font_cfg)
        self.setStyleSheet(ss)
        self._schedule_save()

    def _on_font_changed(self, font_cfg: dict):
        self._font_cfg = font_cfg
        ss = build_stylesheet(self._colors, font_cfg)
        self.setStyleSheet(ss)
        self._schedule_save()

    def _apply_shortcuts(self):
        """Reapplique les raccourcis clavier depuis self._shortcuts."""
        from PyQt6.QtGui import QKeySequence
        sc = self._shortcuts
        # Les actions du menu sont retrouvées et mises à jour
        mapping = {
            'play_pause': self._on_play_pause,
            'stop': self._on_stop,
            'next': self._on_next,
            'prev': self._on_prev,
            'open_file': self.playlist_widget._on_add_files,
            'save_playlist': self.playlist_widget._on_save_playlist,
            'close': self.close,
        }
        # Stocker pour keyPressEvent
        self._shortcut_map = sc

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
        self._schedule_save()

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
            self.sld_volume.setValue(min(150, self.sld_volume.value() + 5))
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
