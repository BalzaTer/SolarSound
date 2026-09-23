"""
Moteur vidéo SolarSound — Qt Multimedia
Gère lecture vidéo + extraction audio vers le pipeline 5.1 SolarSound.

Architecture audio vidéo, par ordre de préférence :

  1. Piste audio extraite séparément et jouée via AudioEngine (pipeline 5.1
     SolarSound, le même que pour les fichiers audio classiques) — c'est ce
     chemin qui donne accès à la spatialisation, l'égaliseur, le vinyle…
     QMediaPlayer → image → QVideoWidget (rendu visuel uniquement)
     QMediaPlayer → audio → QAudioOutput MUET (juste pour garder l'horloge
                             interne de Qt cohérente avec la vidéo)
     AudioEngine  → sd.OutputStream (le son entendu vient de là)

  2. Si l'extraction échoue (cas le plus courant en pratique : la plupart
     des conteneurs vidéo — MP4, MKV… — ne sont pas décodables par
     `soundfile`, qui ne lit que des fichiers audio "nus"), sortie audio
     "boostée" maison :
     QMediaPlayer → QAudioBufferOutput → buffers PCM bruts
                  → gain appliqué en Python (numpy) → QAudioSink

     Pourquoi ne pas simplement utiliser QAudioOutput.setVolume() ici ?
     Parce que cette méthode borne silencieusement sa valeur à [0.0, 1.0]
     côté Qt Multimedia : au-delà de 100%, l'appel ne lève aucune erreur
     mais n'a plus aucun effet. Un vrai gain > 100% nécessite d'appliquer
     le facteur soi-même sur les échantillons avant de les envoyer à la
     sortie audio, d'où ce second pipeline.

  3. Si même ce second pipeline ne fonctionne pas (aucun périphérique
     audio disponible, par exemple), repli ultime sur QAudioOutput direct
     — le volume sera alors plafonné à 100%, mais le son ne sera jamais
     coupé par erreur.
"""

import os
import numpy as np
from typing import Optional, Callable
from dataclasses import dataclass

from PyQt6.QtMultimedia import (
    QMediaPlayer, QAudioOutput, QAudioSink, QAudioFormat, QAudioBufferOutput
)
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, pyqtSignal, QObject, QTimer

try:
    from ..core.volume import SLIDER_MAX, slider_to_gain
except ImportError:
    from core.volume import SLIDER_MAX, slider_to_gain


SUPPORTED_VIDEO_FORMATS = (
    ".mp4", ".mkv", ".avi", ".mov", ".wmv",
    ".m4v", ".flv", ".webm", ".ts", ".m2ts", ".mpg", ".mpeg"
)

SUPPORTED_AUDIO_FORMATS = (
    ".mp3", ".wav", ".flac", ".ogg", ".opus",
    ".aac", ".m4a", ".wma", ".aiff", ".aif"
)

ALL_MEDIA_FORMATS = SUPPORTED_VIDEO_FORMATS + SUPPORTED_AUDIO_FORMATS

# Délai laissé au pipeline "boosté" pour recevoir son premier buffer avant
# de considérer qu'il ne fonctionne pas sur cette machine et de replier
# sur QAudioOutput direct (silence total sinon).
_BOOST_FALLBACK_TIMEOUT_MS = 1500


@dataclass
class VideoConfig:
    speed: float = 1.0
    volume: int = 100
    subtitle_file: str = ""


class VideoEngine(QObject):
    """
    Moteur vidéo Qt Multimedia.
    L'audio de la vidéo est routé vers audio_engine (pipeline 5.1) quand
    l'extraction réussit, sinon vers une sortie audio maison capable d'un
    vrai gain > 100% (voir docstring du module).
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
        # Audio output Qt : reste attaché (muet) même quand on ne l'utilise
        # pas pour le son, Qt s'en sert comme horloge de synchro interne.
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)

        # Sortie audio "boostée" : voir docstring en tête de fichier.
        self._boost_buffer_output = QAudioBufferOutput()
        self._boost_buffer_output.audioBufferReceived.connect(self._on_audio_buffer)
        self._boost_sink = None
        self._boost_sink_io = None
        self._boost_sink_format: Optional[QAudioFormat] = None
        self._boost_fallback_timer = QTimer(self)
        self._boost_fallback_timer.setSingleShot(True)
        self._boost_fallback_timer.timeout.connect(self._on_boost_fallback_timeout)

        # Quel pipeline audio est actif pour la lecture en cours ?
        self._pipeline_active = False  # True = AudioEngine (5.1 SolarSound)
        self._boost_active = False     # True = QAudioBufferOutput + QAudioSink

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
        Sinon, on utilise la sortie audio "boostée" (voir docstring du module).
        """
        try:
            self.stop()
            self._current_path = filepath
            url = QUrl.fromLocalFile(os.path.abspath(filepath))
            self._player.setSource(url)

            # Si on a un moteur audio et que c'est une vidéo,
            # charger la piste audio séparément pour le pipeline 5.1
            pipeline_ok = False
            if self._audio_engine is not None:
                ext = filepath.lower()
                is_video = any(ext.endswith(e) for e in SUPPORTED_VIDEO_FORMATS)
                if is_video:
                    try:
                        pipeline_ok = bool(self._audio_engine.load(filepath))
                    except Exception:
                        pipeline_ok = False

            if pipeline_ok:
                self._set_active_output("pipeline")
            else:
                self._set_active_output("boost")

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
        if self._pipeline_active:
            try:
                self._audio_engine.play()
            except Exception:
                pass

    def pause(self):
        self._was_playing = False
        self._player.pause()
        self.state = self.STATE_PAUSED
        if self._pipeline_active:
            try:
                self._audio_engine.pause()
            except Exception:
                pass

    def stop(self):
        self._was_playing = False
        self._player.stop()
        self.state = self.STATE_STOPPED
        if self._audio_engine:
            try:
                self._audio_engine.stop()
            except Exception:
                pass
        self._set_active_output("direct")

    def seek(self, seconds: float):
        ms = int(seconds * 1000)
        self._player.setPosition(ms)
        if self._pipeline_active:
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
        if self._pipeline_active:
            try:
                if hasattr(self._audio_engine, 'vinyl') and self._audio_engine.vinyl:
                    self._audio_engine.vinyl.config.motor_speed = self.config.speed
            except Exception:
                pass

    def set_volume(self, vol: int | float):
        """
        Applique le volume au pipeline actuellement actif.
        `vol` est la valeur brute du slider (0..125, 100 = volume nominal,
        au-delà = gain réel appliqué numériquement, voir docstring module).
        """
        self.config.volume = max(0, min(SLIDER_MAX, int(vol)))
        gain = self._current_gain()
        if self._pipeline_active:
            if self._audio_engine:
                self._audio_engine.set_volume(gain)
        elif self._boost_active:
            pass  # rien à faire : le gain est relu à chaque buffer reçu
        else:
            # Repli direct Qt : plafonné à 100% (limite de QAudioOutput).
            self._audio_output.setVolume(min(1.0, gain))

    def _current_gain(self) -> float:
        return slider_to_gain(self.config.volume)

    def _apply_config(self):
        self._player.setPlaybackRate(self.config.speed)

    def set_subtitle_file(self, path: str):
        self.config.subtitle_file = path

    # ── Sélection du pipeline audio actif ───────────────────────────────

    def _set_active_output(self, mode: str):
        """
        mode : "pipeline" (AudioEngine 5.1), "boost" (sortie maison, gain
        réel jusqu'à 125%) ou "direct" (QAudioOutput, plafonné à 100%).
        """
        self._boost_fallback_timer.stop()
        self._pipeline_active = (mode == "pipeline")
        self._boost_active = (mode == "boost")

        if mode == "pipeline":
            # Le son sort de l'AudioEngine (sd.OutputStream) : on coupe
            # tout le reste. QAudioOutput reste attaché mais muet, pour que
            # Qt garde une horloge audio cohérente avec l'image.
            self._player.setAudioBufferOutput(None)
            self._stop_boost_sink()
            self._audio_output.setVolume(0.0)
        elif mode == "boost":
            # On coupe QAudioOutput et on route les buffers PCM bruts vers
            # notre propre sortie, avec le vrai gain appliqué dessus.
            self._audio_output.setVolume(0.0)
            self._player.setAudioBufferOutput(self._boost_buffer_output)
            # Filet de sécurité : si aucun buffer n'arrive (périphérique
            # audio indisponible, format non géré…), on ne laisse pas
            # l'utilisateur sans son.
            self._boost_fallback_timer.start(_BOOST_FALLBACK_TIMEOUT_MS)
        else:  # "direct"
            self._player.setAudioBufferOutput(None)
            self._stop_boost_sink()
            self._audio_output.setVolume(min(1.0, self._current_gain()))

    def _on_boost_fallback_timeout(self):
        """Aucun buffer reçu à temps : on abandonne le pipeline boosté."""
        if self._boost_active:
            self._boost_active = False
            self._player.setAudioBufferOutput(None)
            self._stop_boost_sink()
            self._audio_output.setVolume(min(1.0, self._current_gain()))

    def _stop_boost_sink(self):
        if self._boost_sink is not None:
            try:
                self._boost_sink.stop()
            except Exception:
                pass
        self._boost_sink = None
        self._boost_sink_io = None
        self._boost_sink_format = None

    def _on_audio_buffer(self, buffer):
        """
        Reçoit un buffer PCM brut décodé par Qt, lui applique le gain
        courant (potentiellement > 1.0) et l'écrit sur notre propre
        QAudioSink. C'est ce détour qui permet un vrai volume > 100% pour
        la vidéo (voir docstring en tête de fichier).
        """
        if not self._boost_active:
            return
        try:
            self._boost_fallback_timer.stop()  # au moins un buffer est arrivé

            fmt = buffer.format()
            if not fmt.isValid():
                return
            if self._boost_sink is None or self._boost_sink_format != fmt:
                self._stop_boost_sink()
                self._boost_sink = QAudioSink(fmt)
                self._boost_sink_format = fmt
                self._boost_sink_io = self._boost_sink.start()
                if self._boost_sink_io is None:
                    # Pas de périphérique audio exploitable : on abandonne
                    # ce pipeline plutôt que de perdre du son en boucle.
                    self._stop_boost_sink()
                    self._boost_active = False
                    self._player.setAudioBufferOutput(None)
                    self._audio_output.setVolume(min(1.0, self._current_gain()))
                    return

            raw = bytes(buffer.constData())
            if not raw:
                return

            gain = self._current_gain()
            sample_format = fmt.sampleFormat()
            out_bytes = raw

            if abs(gain - 1.0) > 1e-3:
                if sample_format == QAudioFormat.SampleFormat.Float:
                    samples = np.frombuffer(raw, dtype=np.float32).astype(np.float32)
                    samples = np.clip(samples * gain, -1.0, 1.0)
                    out_bytes = samples.astype(np.float32).tobytes()
                elif sample_format == QAudioFormat.SampleFormat.Int16:
                    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                    samples = np.clip(samples * gain, -32768, 32767)
                    out_bytes = samples.astype(np.int16).tobytes()
                elif sample_format == QAudioFormat.SampleFormat.Int32:
                    samples = np.frombuffer(raw, dtype=np.int32).astype(np.float64)
                    samples = np.clip(samples * gain, -2147483648, 2147483647)
                    out_bytes = samples.astype(np.int32).tobytes()
                elif sample_format == QAudioFormat.SampleFormat.UInt8:
                    samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0
                    samples = np.clip(samples * gain, -128.0, 127.0)
                    out_bytes = (samples + 128.0).astype(np.uint8).tobytes()
                # Autre format (inconnu) : on relaie tel quel, sans gain.

            if self._boost_sink_io is not None:
                self._boost_sink_io.write(out_bytes)
        except Exception:
            pass

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
        # Sync audio si décalage > 300ms (uniquement pipeline 5.1 : le
        # pipeline "boosté" suit directement le flux de buffers de Qt,
        # rien à resynchroniser de notre côté).
        if self._pipeline_active:
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
            try:
                self.on_track_ended()
            except Exception:
                pass

    def _dispatch_error(self, msg: str):
        if self.on_error:
            try:
                self.on_error(msg)
            except Exception:
                pass

    def _dispatch_pos(self, pos: float):
        if self.on_position_changed:
            try:
                self.on_position_changed(pos)
            except Exception:
                pass

    def release(self):
        self.stop()
        self._boost_fallback_timer.stop()
        self._stop_boost_sink()
        self._player.setAudioBufferOutput(None)
        self._player.setSource(QUrl())
