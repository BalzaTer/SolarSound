"""
Fenêtre vidéo détachable SolarSound
- Surface de rendu VLC embarquée
- Contrôles superposés (masquables)
- Double-clic → plein écran
- Peut être détachée de la fenêtre principale ou réintégrée
- Sous-titres, vitesse, frame-by-frame accessibles
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QFrame, QSizePolicy, QFileDialog, QComboBox,
    QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QPainter, QFont, QKeyEvent, QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtMultimediaWidgets import QVideoWidget

try:
    from ..video.player import VideoEngine, SUPPORTED_VIDEO_FORMATS
    from ..audio.metadata import format_duration
except (ImportError, ModuleNotFoundError):
    from video.player import VideoEngine, SUPPORTED_VIDEO_FORMATS
    from audio.metadata import format_duration


# ── Surface de rendu (QVideoWidget Qt Multimedia) ───────────────────────────
# QVideoWidget est utilisé directement — pas besoin de classe custom.
# Le moteur VideoEngine.create_video_widget() le crée et le connecte.

# ── Overlay de contrôles (masquable) ────────────────────────────────────────

class ControlsOverlay(QFrame):
    """Barre de contrôles flottante en bas de la surface vidéo."""

    play_pause  = pyqtSignal()
    stop        = pyqtSignal()
    prev        = pyqtSignal()
    next_track  = pyqtSignal()
    seek        = pyqtSignal(float)        # fraction 0–1
    speed_changed = pyqtSignal(float)
    step_fwd    = pyqtSignal()
    step_bwd    = pyqtSignal()
    fullscreen  = pyqtSignal()
    subtitle_load = pyqtSignal()
    detach      = pyqtSignal()

    SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0, 5.0, 8.0, 10.0]

    def __init__(self, icons_dir: str, parent=None):
        super().__init__(parent)
        self._icons_dir = icons_dir
        self._icon_buttons = []
        self._accent = "#f5a623"
        self._seeking = False
        self._setup_ui()

    def _icon(self, name: str):
        path = os.path.join(self._icons_dir, name)
        if name and os.path.isfile(path):
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            QSvgRenderer(path).render(painter)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), QColor(self._accent))
            painter.end()
            return QIcon(pixmap)
        return QIcon()

    def set_theme_colors(self, colors: dict):
        self._accent = colors.get("accent", "#f5a623")
        for button, icon_name in self._icon_buttons:
            button.setIcon(self._icon(icon_name))
        self.sld_progress.setStyleSheet(f"""
            QSlider::groove:horizontal {{ height: 4px; background: {colors.get('border', '#2a2416')}; border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {self._accent}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {self._accent}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
        """)

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: rgba(10, 8, 6, 200);
                border-top: 1px solid #2a2416;
            }
            QPushButton {
                background: transparent;
                border: none;
                color: #e8d5a0;
                font-size: 14px;
                padding: 4px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(245,166,35,60); color: #f5a623; }
            QPushButton:pressed { background: rgba(245,166,35,120); }
            QSlider::groove:horizontal {
                height: 4px; background: #2a2416; border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #f5a623; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #f5a623; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }
            QLabel { color: #e8d5a0; font-family: Consolas; font-size: 11px; }
            QComboBox {
                background: #1e1a12; border: 1px solid #3d3420;
                color: #e8d5a0; padding: 2px 6px; border-radius: 4px;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                background: #1e1a12; color: #e8d5a0;
                selection-background-color: #2a2008;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # ── Barre de progression ──────────────────────────────────────
        prog_row = QHBoxLayout()
        self.lbl_pos = QLabel("0:00")
        self.lbl_pos.setFixedWidth(50)
        prog_row.addWidget(self.lbl_pos)

        self.sld_progress = QSlider(Qt.Orientation.Horizontal)
        self.sld_progress.setRange(0, 10000)
        self.sld_progress.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self.sld_progress.sliderReleased.connect(self._on_seek_release)
        prog_row.addWidget(self.sld_progress)

        self.lbl_dur = QLabel("0:00")
        self.lbl_dur.setFixedWidth(50)
        self.lbl_dur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog_row.addWidget(self.lbl_dur)
        layout.addLayout(prog_row)

        # ── Boutons transport ─────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(2)

        def btn(icon_name, fallback_text, tooltip, signal):
            b = QPushButton()
            ic = self._icon(icon_name)
            if ic.isNull():
                b.setText(fallback_text)
            else:
                b.setIcon(ic)
                from PyQt6.QtCore import QSize
                b.setIconSize(QSize(18, 18))
            b.setToolTip(tooltip)
            b.setFixedSize(32, 32)
            b.clicked.connect(signal)
            if icon_name:
                self._icon_buttons.append((b, icon_name))
            return b

        self.btn_prev   = btn("preview.svg",    "⏮", "Précédent",         self.prev)
        self.btn_step_b = btn("",               "◁|", "Image précédente", self.step_bwd)
        self.btn_stop   = btn("stop.svg",       "■",  "Stop",              self.stop)
        self.btn_play   = btn("play.svg",       "▶",  "Lecture/Pause",    self.play_pause)
        self.btn_step_f = btn("",               "|▷", "Image suivante",   self.step_fwd)
        self.btn_next   = btn("next.svg",       "⏭", "Suivant",           self.next_track)

        self.btn_step_b.setText("◁|")
        self.btn_step_f.setText("|▷")
        self.btn_step_b.setStyleSheet("font-size: 11px; font-weight: bold;")
        self.btn_step_f.setStyleSheet("font-size: 11px; font-weight: bold;")

        for b in [self.btn_prev, self.btn_step_b, self.btn_stop,
                  self.btn_play, self.btn_step_f, self.btn_next]:
            btn_row.addWidget(b)

        btn_row.addSpacing(8)

        # Vitesse
        lbl_spd = QLabel("Vitesse:")
        btn_row.addWidget(lbl_spd)
        self.cmb_speed = QComboBox()
        for s in self.SPEEDS:
            self.cmb_speed.addItem(f"{s}x", s)
        self.cmb_speed.setCurrentIndex(self.SPEEDS.index(1.0))
        self.cmb_speed.currentIndexChanged.connect(
            lambda i: self.speed_changed.emit(self.cmb_speed.itemData(i))
        )
        self.cmb_speed.setFixedWidth(70)
        btn_row.addWidget(self.cmb_speed)

        btn_row.addSpacing(8)

        # Sous-titres
        self.btn_sub = QPushButton("💬")
        self.btn_sub.setToolTip("Charger sous-titres (.srt/.ass)")
        self.btn_sub.setFixedSize(32, 32)
        self.btn_sub.clicked.connect(self.subtitle_load)
        btn_row.addWidget(self.btn_sub)

        btn_row.addStretch()

        # Détacher / Plein écran
        self.btn_detach = QPushButton("⧉")
        self.btn_detach.setToolTip("Détacher la fenêtre vidéo")
        self.btn_detach.setFixedSize(32, 32)
        self.btn_detach.clicked.connect(self.detach)
        btn_row.addWidget(self.btn_detach)

        self.btn_fs = QPushButton("⛶")
        self.btn_fs.setToolTip("Plein écran (F)")
        self.btn_fs.setFixedSize(32, 32)
        self.btn_fs.clicked.connect(self.fullscreen)
        btn_row.addWidget(self.btn_fs)

        layout.addLayout(btn_row)

    def _on_seek_release(self):
        self._seeking = False
        frac = self.sld_progress.value() / 10000.0
        self.seek.emit(frac)

    def update_position(self, pos_sec: float, dur_sec: float):
        if self._seeking:
            return
        if dur_sec > 0:
            self.sld_progress.setValue(int(pos_sec / dur_sec * 10000))
        self.lbl_pos.setText(format_duration(pos_sec))
        self.lbl_dur.setText(format_duration(dur_sec))

    def set_playing(self, playing: bool):
        from PyQt6.QtGui import QIcon
        icon_name = "pause.svg" if playing else "play.svg"
        ic = self._icon(icon_name)
        if not ic.isNull():
            self.btn_play.setIcon(ic)
        else:
            self.btn_play.setText("⏸" if playing else "▶")

    def set_speed(self, speed: float):
        # Trouver la vitesse la plus proche
        idx = min(range(len(self.SPEEDS)),
                  key=lambda i: abs(self.SPEEDS[i] - speed))
        self.cmb_speed.setCurrentIndex(idx)


# ── Fenêtre vidéo détachable ─────────────────────────────────────────────────

class VideoWindow(QWidget):
    """
    Fenêtre vidéo qui peut fonctionner :
    - En mode intégré : widget dans la fenêtre principale
    - En mode détaché : QWidget indépendant flottant

    Signaux remontés vers MainWindow pour contrôle de playlist.
    """

    request_prev   = pyqtSignal()
    request_next   = pyqtSignal()
    request_stop   = pyqtSignal()

    HIDE_CONTROLS_DELAY = 2500  # ms avant de masquer les contrôles

    def __init__(self, engine: VideoEngine, icons_dir: str, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._icons_dir = icons_dir
        self._detached = False
        self._fullscreen = False
        self._controls_visible = True

        self.setMinimumSize(320, 240)
        self.setStyleSheet("background: #000;")

        # Timer masquage contrôles
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(self.HIDE_CONTROLS_DELAY)
        self._hide_timer.timeout.connect(self._hide_controls)

        self._setup_ui()
        self._connect_engine()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Surface vidéo Qt Multimedia
        self.surface = self.engine.create_video_widget()
        self.surface.setMouseTracking(True)
        self.surface.mouseDoubleClickEvent = lambda e: self._toggle_fullscreen()
        self.surface.mouseMoveEvent = lambda e: self._show_controls_temp()
        layout.addWidget(self.surface, stretch=1)

        # Overlay contrôles
        self.controls = ControlsOverlay(self._icons_dir)
        self.controls.play_pause.connect(self._on_play_pause)
        self.controls.stop.connect(self.request_stop)
        self.controls.prev.connect(self.request_prev)
        self.controls.next_track.connect(self.request_next)
        self.controls.seek.connect(self._on_seek)
        self.controls.speed_changed.connect(self.engine.set_speed)
        self.controls.step_fwd.connect(self.engine.step_forward)
        self.controls.step_bwd.connect(self.engine.step_backward)
        self.controls.fullscreen.connect(self._toggle_fullscreen)
        self.controls.subtitle_load.connect(self._load_subtitle)
        self.controls.detach.connect(self.toggle_detach)
        layout.addWidget(self.controls)

        # Timer update UI
        self._ui_timer = QTimer()
        self._ui_timer.setInterval(200)
        self._ui_timer.timeout.connect(self._update_ui)
        self._ui_timer.start()

    def _connect_engine(self):
        self.engine.on_track_ended = self._on_engine_ended

    # ── Surface de rendu (no-op avec Qt Multimedia) ──────────────────
    def attach_renderer(self):
        """No-op : Qt Multimedia gere le rendu automatiquement."""
        pass

    # ── Contrôle lecture ──────────────────────────────────────────────
    def _on_play_pause(self):
        if self.engine.state == VideoEngine.STATE_PLAYING:
            self.engine.pause()
            self.controls.set_playing(False)
        elif self.engine.state == VideoEngine.STATE_PAUSED:
            self.engine.play()
            self.controls.set_playing(True)

    def _on_seek(self, frac: float):
        dur = self.engine.duration_seconds
        self.engine.seek(frac * dur)

    def notify_playing(self):
        self.controls.set_playing(True)

    def notify_stopped(self):
        self.controls.set_playing(False)

    def _on_engine_ended(self):
        try:
            QTimer.singleShot(0, self._handle_ended)
        except Exception:
            try:
                self._handle_ended()
            except Exception:
                pass

    def _handle_ended(self):
        try:
            self.controls.set_playing(False)
            self.request_next.emit()
        except Exception:
            pass

    # ── Sous-titres ───────────────────────────────────────────────────
    def _load_subtitle(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Charger des sous-titres",
            "", "Sous-titres (*.srt *.ass *.ssa *.sub *.vtt);;Tous (*.*)"
        )
        if path:
            self.engine.set_subtitle_file(path)

    # ── UI update ─────────────────────────────────────────────────────
    def _update_ui(self):
        pos = self.engine.position_seconds
        dur = self.engine.duration_seconds
        self.controls.update_position(pos, dur)

    # ── Plein écran ───────────────────────────────────────────────────
    def _toggle_fullscreen(self):
        if not self._detached:
            self.toggle_detach()
            return
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self.showFullScreen()
            self._show_controls_temp()
        else:
            self.showNormal()

    # ── Détachement ───────────────────────────────────────────────────
    def toggle_detach(self):
        if not self._detached:
            self.detach()
        else:
            self.reattach()

    def detach(self):
        self._detached = True
        self.setWindowTitle("SolarSound — Lecteur Vidéo")
        self.setWindowFlags(Qt.WindowType.Window)
        self.controls.btn_detach.setToolTip("Réintégrer dans la fenêtre principale")
        self.controls.btn_detach.setText("⧈")
        self.resize(900, 600)
        self.show()
        QTimer.singleShot(100, self.attach_renderer)

    def reattach(self):
        self._detached = False
        self.setWindowFlags(Qt.WindowType.Widget)
        self.controls.btn_detach.setToolTip("Détacher la fenêtre vidéo")
        self.controls.btn_detach.setText("⧉")
        if self._fullscreen:
            self._fullscreen = False
        self.show()

    # ── Contrôles auto-masquage ───────────────────────────────────────
    def _show_controls_temp(self):
        self.controls.setVisible(True)
        self._controls_visible = True
        if self._fullscreen:
            self._hide_timer.start()

    def _hide_controls(self):
        if self._fullscreen and self.engine.state == VideoEngine.STATE_PLAYING:
            self.controls.setVisible(False)
            self._controls_visible = False

    # ── Clavier ───────────────────────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        try:
            key = event.key()
            if key == Qt.Key.Key_F:
                self._toggle_fullscreen()
            elif key == Qt.Key.Key_Escape and self._fullscreen:
                self._toggle_fullscreen()
            elif key == Qt.Key.Key_Space:
                self._on_play_pause()
            elif key == Qt.Key.Key_Period:
                self.engine.step_forward()
            elif key == Qt.Key.Key_Comma:
                self.engine.step_backward()
            else:
                super().keyPressEvent(event)
        except Exception:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self._detached:
            # Réintégrer plutôt que fermer
            self.reattach()
            event.ignore()
        else:
            event.accept()

    def showEvent(self, event):
        super().showEvent(event)
