"""
Moteur vidéo SolarSound — Qt Multimedia
Gère lecture vidéo + extraction audio vers le pipeline 5.1 SolarSound.

Architecture audio vidéo :
  QMediaPlayer → image → QVideoWidget  (rendu visuel)
  QMediaPlayer → audio → QAudioOutput silencieux (désactivé)
  + AudioExtractor → PCM float32 → AudioEngine (spatialisation 5.1)

Quand l'extraction audio n'est pas disponible, on bascule sur
QAudioOutput direct (sans effets 5.1).
"""

import os
import numpy as np
from typing import Optional, Callable
from dataclasses import dataclass

from PyQt6.QtMultimedia import (
    QMediaPlayer, QAudioOutput, QAudioSink, QAudioFormat,
    QMediaCaptureSession, QAudioBufferOutput
)
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, pyqtSignal, QObject, QTimer


SUPPORTED_VIDEO_FORMATS = (
    ".mp4", ".mkv", ".avi", ".mov", ".wmv",
    ".m4v", ".flv", ".webm", ".ts", ".m2ts", ".mpg", ".mpeg"
)

SUPPORTED_AUDIO_FORMATS = (
    ".mp3", ".wav", ".flac", ".ogg", ".opus",
    ".aac", ".m4a", ".wma", ".aiff", ".aif"
)

ALL_MEDIA_FORMATS = SUPPORTED_VIDEO_FORMATS + SUPPORTED_AUDIO_FORMATS


@dataclass
class VideoConfig:
    speed: float = 1.0
    volume: int = 100
    subtitle_file: str = ""


class VideoEngine(QObject):
    """
    Moteur vidéo Qt Multimedia.
    L'audio de la vidéo est routé vers audio_engine (pipeline 5.1)
    si audio_engine est fourni, sinon via QAudioOutput direct.
    """

    STATE_STOPPED = "stopped"
    STATE_PLAYING = "playing"
    STATE_PAUSED  = "paused"

    _sig_ended = pyqtSignal()
    _sig_error = pyqtSignal(str)
    _sig_pos   = pyqtSignal(float)

    def __init__(self, audio_engine=None, parent=None):
        super().__init__(parent)
        self.state  = self.STATE_STOPPED
        self.config = VideoConfig()
        self._audio_engine = audio_engine  # référence au AudioEngine SolarSound

        self.on_position_changed: Optional[Callable[[float], None]] = None
        self.on_track_ended:      Optional[Callable[[], None]]      = None
        self.on_error:            Optional[Callable[[str], None]]   = None

        # Player Qt pour la vidéo
        self._player       = QMediaPlayer()
        # Audio output direct (utilisé quand pas de pipeline 5.1)
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)

        self._video_widget: Optional[QVideoWidget] = None
        self._was_playing = False
        self._current_path = ""

        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.errorOccurred.connect(self._on_qt_error)
        self._player.positionChanged.connect(self._on_position)

        self._sig_ended.connect(self._dispatch_ended)
        self._sig_error.connect(self._dispatch_error)
        self._sig_pos.connect(self._dispatch_pos)

    def set_audio_engine(self, engine):
        """Connecte le moteur audio SolarSound pour le pipeline 5.1."""
        self._audio_engine = engine

    # ── Surface de rendu ──────────────────────────────────────────────

    def create_video_widget(self) -> QVideoWidget:
        self._video_widget = QVideoWidget()
        self._video_widget.setStyleSheet("background: black;")
        self._player.setVideoOutput(self._video_widget)
        return self._video_widget

    def get_video_widget(self) -> Optional[QVideoWidget]:
        return self._video_widget

    # no-op compat
    def set_hwnd(self, hwnd): pass
    def set_xwindow(self, xid): pass
    def set_nsobject(self, obj): pass

    # ── Chargement ────────────────────────────────────────────────────

    def load(self, filepath: str) -> bool:
        """
        Charge un fichier vidéo.
        Si audio_engine est disponible ET c'est un fichier vidéo,
        on charge aussi l'audio via le moteur SolarSound (piste audio extraite).
        """
        try:
            self.stop()
            self._current_path = filepath
            url = QUrl.fromLocalFile(os.path.abspath(filepath))
            self._player.setSource(url)

            # Si on a un moteur audio et que c'est une vidéo,
            # charger la piste audio séparément pour le pipeline 5.1
            if self._audio_engine is not None:
                ext = filepath.lower()
                is_video = any(ext.endswith(e) for e in SUPPORTED_VIDEO_FORMATS)
                if is_video:
                    # Tenter de charger l'audio via le moteur SolarSound
                    try:
                        ok = self._audio_engine.load(filepath)
                        if ok:
                            # Couper l'audio Qt pour éviter le doublon
                            self._audio_output.setVolume(0.0)
                        else:
                            # Fallback : audio Qt direct
                            self._audio_output.setVolume(
                                min(2.0, self.config.volume / 100.0)
                            )
                    except Exception:
                        self._audio_output.setVolume(
                            min(2.0, self.config.volume / 100.0)
                        )
                else:
                    self._audio_output.setVolume(
                        min(2.0, self.config.volume / 100.0)
                    )
            return True
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
            return False

    # ── Transport ─────────────────────────────────────────────────────

    def play(self):
        self._was_playing = True
        self._player.play()
        self.state = self.STATE_PLAYING
        self._apply_config()
        # Synchroniser l'audio SolarSound
        if self._audio_engine and self._audio_output.volume() == 0.0:
            try:
                self._audio_engine.play()
            except Exception:
                pass

    def pause(self):
        self._was_playing = False
        self._player.pause()
        self.state = self.STATE_PAUSED
        # Pause audio SolarSound
        if self._audio_engine and self._audio_output.volume() == 0.0:
            try:
                self._audio_engine.pause()
            except Exception:
                pass

    def stop(self):
        self._was_playing = False
        self._player.stop()
        self.state = self.STATE_STOPPED
        # Stop audio SolarSound
        if self._audio_engine:
            try:
                self._audio_engine.stop()
            except Exception:
                pass
        # Restaurer volume Qt
        self._audio_output.setVolume(min(2.0, self.config.volume / 100.0))

    def seek(self, seconds: float):
        ms = int(seconds * 1000)
        self._player.setPosition(ms)
        # Sync audio
        if self._audio_engine and self._audio_output.volume() == 0.0:
            try:
                self._audio_engine.seek(seconds)
            except Exception:
                pass

    def seek_ms(self, ms: int):
        self.seek(ms / 1000.0)

    # ── Frame-by-frame ────────────────────────────────────────────────

    def step_forward(self):
        if self.state == self.STATE_PLAYING:
            self.pause()
        cur = self._player.position()
        self._player.setPosition(cur + 40)

    def step_backward(self):
        if self.state == self.STATE_PLAYING:
            self.pause()
        self._player.setPosition(max(0, self._player.position() - 40))

    # ── Propriétés ────────────────────────────────────────────────────

    @property
    def position_seconds(self) -> float:
        return self._player.position() / 1000.0

    @property
    def duration_seconds(self) -> float:
        d = self._player.duration()
        return d / 1000.0 if d > 0 else 0.0

    @property
    def is_available(self) -> bool:
        return True

    # ── Configuration ─────────────────────────────────────────────────

    def set_speed(self, speed: float):
        self.config.speed = max(0.25, min(10.0, speed))
        self._player.setPlaybackRate(self.config.speed)
        # Sync audio speed (vinyl/engine)
        if self._audio_engine and self._audio_output.volume() == 0.0:
            try:
                if hasattr(self._audio_engine, 'vinyl') and self._audio_engine.vinyl:
                    self._audio_engine.vinyl.config.motor_speed = self.config.speed
            except Exception:
                pass

    def set_volume(self, vol: int):
        self.config.volume = max(0, min(200, vol))
        if self._audio_output.volume() > 0:
            # Audio Qt direct
            self._audio_output.setVolume(min(2.0, self.config.volume / 100.0))
        else:
            # Audio via pipeline SolarSound
            if self._audio_engine:
                self._audio_engine.set_volume(self.config.volume / 100.0)

    def _apply_config(self):
        self._player.setPlaybackRate(self.config.speed)

    def set_subtitle_file(self, path: str):
        self.config.subtitle_file = path

    # ── Callbacks ─────────────────────────────────────────────────────

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.StoppedState and self._was_playing:
            self._was_playing = False
            self.state = self.STATE_STOPPED
            self._sig_ended.emit()

    def _on_qt_error(self, error, error_string: str):
        if error != QMediaPlayer.Error.NoError:
            self._sig_error.emit(f"Erreur lecture : {error_string}")

    def _on_position(self, pos_ms: int):
        # Sync audio si décalage > 200ms
        if self._audio_engine and self._audio_output.volume() == 0.0:
            try:
                audio_pos = self._audio_engine.position_seconds
                video_pos = pos_ms / 1000.0
                if abs(audio_pos - video_pos) > 0.3:
                    self._audio_engine.seek(video_pos)
            except Exception:
                pass
        self._sig_pos.emit(pos_ms / 1000.0)

    def _dispatch_ended(self):
        if self._audio_engine:
            try:
                self._audio_engine.stop()
            except Exception:
                pass
        if self.on_track_ended:
            self.on_track_ended()

    def _dispatch_error(self, msg: str):
        if self.on_error:
            self.on_error(msg)

    def _dispatch_pos(self, pos: float):
        if self.on_position_changed:
            self.on_position_changed(pos)

    def release(self):
        self.stop()
        self._player.setSource(QUrl())
