"""
Moteur audio SolarSound
Gère la lecture MP3/WAV et la spatialisation 5.1 via sounddevice + numpy.

Canaux de sortie (ordre standard 5.1) :
  0 = Front Left  (FL)
  1 = Front Right (FR)
  2 = Center      (C)
  3 = LFE / Caisson de basse
  4 = Surround Left  (SL)
  5 = Surround Right (SR)
"""

import threading
import queue
import numpy as np
from dataclasses import dataclass
from typing import Optional, Callable
import time
import wave as _wave_mod

try:
    import sounddevice as sd
    SOUNDDEVICE_OK = True
except Exception:
    SOUNDDEVICE_OK = False

try:
    import soundfile as sf
    SOUNDFILE_OK = True
except Exception:
    sf = None
    SOUNDFILE_OK = False

# Formats audio supportes nativement par soundfile
SOUNDFILE_FORMATS = ('.wav', '.mp3', '.flac', '.ogg', '.opus',
                     '.aiff', '.aif', '.au', '.rf64', '.w64')


CHUNK = 2048  # frames par bloc

try:
    from .vinyl import VinylProcessor, VinylConfig
    VINYL_OK = True
except ModuleNotFoundError:
    try:
        from audio.vinyl import VinylProcessor, VinylConfig
        VINYL_OK = True
    except Exception:
        VINYL_OK = False
except Exception:
    VINYL_OK = False


@dataclass
class SpatialConfig:
    """Paramètres de spatialisation 5.1"""
    # Gains par canal (0.0 → 2.0, défaut 1.0)
    gain_fl: float = 1.0
    gain_fr: float = 1.0
    gain_c:  float = 0.0   # Centre – optionnel
    gain_lfe: float = 0.8  # Caisson
    gain_sl: float = 0.8   # Surround L
    gain_sr: float = 0.8   # Surround R

    # Mode double-front sur surround
    double_front_to_surround: bool = True
    surround_blend: float = 0.6   # Ratio copie avant→surround

    # Mode mixage mono → LFE
    mix_to_lfe: bool = True
    lfe_low_pass_hz: float = 80.0  # Fréquence de coupure passe-bas LFE
    lfe_gain: float = 1.0

    # Volume global
    master_volume: float = 1.0

    # ── Stéréo ────────────────────────────────────────────────────────────
    stereo_separation: float = 1.0  # 0.0=mono, 1.0=stéréo normal (angle 0°→180°)
    mix_mono: bool = False           # Forcer mixage mono (L+R)/2 sur toutes enceintes
    invert_stereo: bool = False      # Échanger L et R

    # ── Rotation orbitale ──────────────────────────────────────────────
    rotation_enabled: bool = False
    rotation_speed: float = 0.1   # tours/seconde (0.01 → 2.0)
    rotation_spread: float = 0.5  # étalement angulaire (0.0=1 enceinte, 1.0=3 enceintes)


class LowPassFilter:
    """Filtre Butterworth 1er ordre simplifié pour le LFE"""
    def __init__(self, cutoff_hz: float, sample_rate: int):
        self.set(cutoff_hz, sample_rate)
        self._prev = 0.0

    def set(self, cutoff_hz: float, sample_rate: int):
        rc = 1.0 / (2.0 * np.pi * cutoff_hz)
        dt = 1.0 / sample_rate
        self.alpha = dt / (rc + dt)

    def process(self, data: np.ndarray) -> np.ndarray:
        out = np.empty_like(data)
        prev = self._prev
        a = self.alpha
        for i in range(len(data)):
            prev = prev + a * (data[i] - prev)
            out[i] = prev
        self._prev = prev
        return out


class AudioEngine:
    """Moteur de lecture audio avec spatialisation 5.1"""

    STATE_STOPPED = "stopped"
    STATE_PLAYING = "playing"
    STATE_PAUSED  = "paused"

    def __init__(self):
        self.state = self.STATE_STOPPED
        self.config = SpatialConfig()

        self._audio_data: Optional[np.ndarray] = None
        self._sample_rate: int = 44100
        self._position: int = 0  # frames
        self._total_frames: int = 0

        self._lock = threading.Lock()
        self._stream: Optional[object] = None
        self._lpf = LowPassFilter(self.config.lfe_low_pass_hz, self._sample_rate)

        # Callbacks
        self.on_position_changed: Optional[Callable[[float], None]] = None
        self.on_track_ended: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        self._simulation_mode = not SOUNDDEVICE_OK
        # Processeur vinyle
        self.vinyl = VinylProcessor(self._sample_rate) if VINYL_OK else None
        self._rotation_angle: float = 0.0   # angle courant en radians
        self._sim_thread: Optional[threading.Thread] = None
        self._sim_running = False

    # ── Chargement ────────────────────────────────────────────────────
    def load(self, filepath: str) -> bool:
        """Charge un fichier audio (MP3 ou WAV) en mémoire"""
        self.stop()
        try:
            data, sr = self._decode_file(filepath)
            if data is None:
                return False
            with self._lock:
                self._audio_data = data.astype(np.float32) / 32768.0
                self._sample_rate = sr
                self._position = 0
                self._total_frames = len(self._audio_data)
                self._lpf.set(self.config.lfe_low_pass_hz, sr)
                if self.vinyl:
                    self.vinyl.set_sample_rate(sr)
                    self.vinyl.reset_position()
            return True
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
            return False

    def _decode_file(self, filepath: str):
        """
        Decodeur universel : soundfile d'abord, puis fallback stdlib wave.
        Formats : WAV, MP3, FLAC, OGG, OPUS, AIFF, AU et plus.
        """
        last_error: Optional[Exception] = None

        if not SOUNDFILE_OK:
            last_error = RuntimeError("module soundfile indisponible (import a echoue au demarrage)")
        else:
            try:
                return self._decode_soundfile(filepath)
            except Exception as e:
                last_error = e

        if filepath.lower().endswith('.wav'):
            try:
                return self._decode_wav_stdlib(filepath)
            except Exception as e:
                last_error = e

        raise RuntimeError(
            f"Format non supporte ou fichier illisible : {filepath}\n"
            f"Formats supportes : WAV MP3 FLAC OGG OPUS AIFF\n"
            f"Cause : {last_error}"
        )

    def _decode_soundfile(self, filepath: str):
        """Decode via soundfile : WAV, MP3, FLAC, OGG, AIFF..."""
        data, sr = sf.read(filepath, dtype='float32', always_2d=True)
        if data.shape[1] == 1:
            data = np.column_stack([data[:, 0], data[:, 0]])
        elif data.shape[1] > 2:
            data = data[:, :2]
        data_int16 = (data * 32767).clip(-32768, 32767).astype(np.int16)
        return data_int16, sr

    def _decode_wav_stdlib(self, filepath: str):
        """Fallback stdlib wave pour WAV brut."""
        with _wave_mod.open(filepath, 'rb') as f:
            sr  = f.getframerate()
            ch  = f.getnchannels()
            sw  = f.getsampwidth()
            raw = f.readframes(f.getnframes())
        if sw == 1:
            data = (np.frombuffer(raw, dtype=np.uint8).astype(np.int16) - 128) * 256
        elif sw == 2:
            data = np.frombuffer(raw, dtype=np.int16).copy()
        elif sw == 3:
            n = len(raw) // 3
            data = np.array(
                [int.from_bytes(raw[i*3:(i+1)*3], 'little', signed=True) >> 8
                 for i in range(n)], dtype=np.int16)
        elif sw == 4:
            data = (np.frombuffer(raw, dtype=np.int32) >> 16).astype(np.int16)
        else:
            raise ValueError(f'sample_width={sw} non supporte')
        if ch == 1:
            data = np.column_stack([data, data])
        else:
            data = data.reshape(-1, ch)[:, :2]
        return data, sr

    # ── Lecture / Contrôle ────────────────────────────────────────────
    def play(self):
        if self._audio_data is None:
            return
        if self.state == self.STATE_PAUSED:
            self.state = self.STATE_PLAYING
            if not self._simulation_mode:
                self._start_stream()
            else:
                self._start_simulation()
            return
        if self.state == self.STATE_STOPPED:
            with self._lock:
                self._position = 0
            self.state = self.STATE_PLAYING
            if not self._simulation_mode:
                self._start_stream()
            else:
                self._start_simulation()

    def pause(self):
        if self.state == self.STATE_PLAYING:
            self.state = self.STATE_PAUSED
            self._stop_stream()

    def stop(self):
        self.state = self.STATE_STOPPED
        self._stop_stream()
        with self._lock:
            self._position = 0

    def seek(self, seconds: float):
        with self._lock:
            self._position = max(0, min(int(seconds * self._sample_rate),
                                        self._total_frames - 1))
        if self.vinyl:
            self.vinyl.reset_position()

    @property
    def position_seconds(self) -> float:
        return self._position / max(1, self._sample_rate)

    @property
    def duration_seconds(self) -> float:
        return self._total_frames / max(1, self._sample_rate)

    # ── Spatialisation ────────────────────────────────────────────────
    def _spatialize(self, stereo_chunk: np.ndarray) -> np.ndarray:
        """
        Transforme un bloc stéréo (N×2 float32) en 6 canaux 5.1 (N×6 float32).
        Ordre canaux : FL, FR, C, LFE, SL, SR

        Si la rotation orbitale est activée, les 4 enceintes principales (FL, FR, SL, SR)
        reçoivent des gains dynamiques basés sur l'angle courant.
        L occupe la position θ, R occupe la position θ+π (opposé).
        L'étalement (spread) contrôle combien d'enceintes participent simultanément.
        """
        cfg = self.config
        n = len(stereo_chunk)
        L_raw = stereo_chunk[:, 0]
        R_raw = stereo_chunk[:, 1]

        # ── Pré-traitement stéréo ────────────────────────────────────
        # Inversion L/R
        if cfg.invert_stereo:
            L_raw, R_raw = R_raw, L_raw

        # Mixage mono : (L+R)/2 sur les deux canaux
        if cfg.mix_mono:
            mono = (L_raw + R_raw) * 0.5
            L = mono
            R = mono
        else:
            # Séparation stéréo : 0.0 = mono, 1.0 = stéréo complet
            # Mid/Side : M=(L+R)/2, S=(L-R)/2 ; L=M+s*S, R=M-s*S
            if cfg.stereo_separation < 0.9999:
                s = cfg.stereo_separation
                M = (L_raw + R_raw) * 0.5
                S = (L_raw - R_raw) * 0.5
                L = M + s * S
                R = M - s * S
            else:
                L = L_raw
                R = R_raw

        out = np.zeros((n, 6), dtype=np.float32)

        if cfg.rotation_enabled:
            # ── Mode rotation orbitale ────────────────────────────────
            # Angles fixes des 4 enceintes dans le plan horizontal (sens horaire)
            # FL=0°, FR=90°, SR=180°, SL=270°  (en radians)
            SPEAKER_ANGLES = np.array([0.0, np.pi/2, np.pi, 3*np.pi/2])
            # Correspondance : FL=ch0, FR=ch1, SR=ch5, SL=ch4
            SPEAKER_CHANNELS_L = [0, 1, 5, 4]   # canal pour L
            SPEAKER_CHANNELS_R = [0, 1, 5, 4]   # canal pour R (même anneau, offset π)

            # spread: 0.0 → focus maximum (cos^16), 1.0 → large (cos^1)
            # On interpole l'exposant : spread=0 → exp=16, spread=1 → exp=1
            exponent = max(1.0, 16.0 * (1.0 - cfg.rotation_spread) + 1.0 * cfg.rotation_spread)

            # Avancer l'angle : Δθ = 2π * speed / sr  par frame
            delta_angle = 2.0 * np.pi * cfg.rotation_speed / self._sample_rate

            # Calculer les gains sample par sample pour une transition douce
            # (on fait par bloc, pas par sample, la variation est négligeable à l'échelle d'un chunk)
            theta_L = self._rotation_angle
            theta_R = self._rotation_angle + np.pi   # R est à l'opposé de L

            for i, angle in enumerate(SPEAKER_ANGLES):
                ch = SPEAKER_CHANNELS_L[i]
                # Gain basé sur la proximité angulaire (distance sur le cercle)
                diff_L = angle - theta_L
                diff_R = angle - theta_R
                gain_L = float(np.abs(np.cos(diff_L / 2.0)) ** exponent)
                gain_R = float(np.abs(np.cos(diff_R / 2.0)) ** exponent)
                out[:, ch] += L * gain_L + R * gain_R

            # Avancer l'angle pour le prochain bloc
            self._rotation_angle = (self._rotation_angle + delta_angle * n) % (2.0 * np.pi)

            # Centre et LFE non affectés par la rotation
            if cfg.gain_c > 0:
                out[:, 2] = ((L + R) * 0.5) * cfg.gain_c
            if cfg.mix_to_lfe:
                mono = (L + R) * 0.5
                filtered = self._lpf.process(mono)
                out[:, 3] = filtered * cfg.gain_lfe * cfg.lfe_gain

        else:
            # ── Mode statique classique ───────────────────────────────
            out[:, 0] = L * cfg.gain_fl
            out[:, 1] = R * cfg.gain_fr

            if cfg.gain_c > 0:
                out[:, 2] = ((L + R) * 0.5) * cfg.gain_c

            if cfg.mix_to_lfe:
                mono = (L + R) * 0.5
                filtered = self._lpf.process(mono)
                out[:, 3] = filtered * cfg.gain_lfe * cfg.lfe_gain

            if cfg.double_front_to_surround:
                out[:, 4] = L * cfg.surround_blend * cfg.gain_sl
                out[:, 5] = R * cfg.surround_blend * cfg.gain_sr
            else:
                out[:, 4] = L * cfg.gain_sl
                out[:, 5] = R * cfg.gain_sr

        # Volume master
        out *= cfg.master_volume
        return np.clip(out, -1.0, 1.0)

    # ── Stream sounddevice ────────────────────────────────────────────
    def _start_stream(self):
        self._stop_stream()
        try:
            # Chercher un périphérique 5.1 (6 canaux)
            dev_id = self._find_51_device()
            n_out = 6 if dev_id is not None else 2

            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=n_out,
                dtype="float32",
                blocksize=CHUNK,
                device=dev_id,
                callback=self._audio_callback,
                finished_callback=self._stream_finished,
            )
            self._stream.start()
        except Exception as e:
            self._simulation_mode = True
            self._start_simulation()

    def _find_51_device(self) -> Optional[int]:
        try:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d["max_output_channels"] >= 6:
                    return i
        except Exception:
            pass
        return None

    def _audio_callback(self, outdata, frames, time_info, status):
        with self._lock:
            if self.state != self.STATE_PLAYING or self._audio_data is None:
                outdata[:] = 0
                return

            remaining = self._total_frames - self._position
            if remaining <= 0:
                outdata[:] = 0
                raise sd.CallbackStop()

            n = min(frames, remaining)
            chunk = self._audio_data[self._position: self._position + n]
            self._position += n

        # Effet vinyle (avant spatialisation)
        if self.vinyl and self.vinyl.config.enabled:
            chunk = self.vinyl.process(chunk)

        # Spatialisation
        spat = self._spatialize(chunk)
        n_out = outdata.shape[1]

        if n_out >= 6:
            outdata[:n] = spat
        else:
            # Fallback stéréo
            outdata[:n, 0] = spat[:, 0]
            outdata[:n, 1] = spat[:, 1]

        if n < frames:
            outdata[n:] = 0

        # Notification position
        pos_sec = self._position / self._sample_rate
        if self.on_position_changed:
            self.on_position_changed(pos_sec)

    def _stream_finished(self):
        if self.state == self.STATE_PLAYING:
            self.state = self.STATE_STOPPED
            if self.on_track_ended:
                self.on_track_ended()

    def _stop_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    # ── Mode simulation (sans carte son) ─────────────────────────────
    def _start_simulation(self):
        self._sim_running = True
        self._sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
        self._sim_thread.start()

    def _sim_loop(self):
        """Simule la progression de lecture sans audio réel"""
        while self._sim_running and self.state == self.STATE_PLAYING:
            with self._lock:
                self._position += CHUNK
                if self._position >= self._total_frames:
                    self._position = self._total_frames
                    pos_sec = self.position_seconds
                else:
                    pos_sec = self.position_seconds
            if self.on_position_changed:
                self.on_position_changed(pos_sec)
            if self._position >= self._total_frames:
                self.state = self.STATE_STOPPED
                if self.on_track_ended:
                    self.on_track_ended()
                break
            time.sleep(CHUNK / self._sample_rate)
        self._sim_running = False

    def set_volume(self, vol: float):
        self.config.master_volume = max(0.0, min(2.0, vol))

    def update_lpf(self):
        self._lpf.set(self.config.lfe_low_pass_hz, self._sample_rate)
