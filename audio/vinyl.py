"""
Moteur d'effet vinyle SolarSound
====================================
Trois couches d'effet indépendantes, toutes appliquées sample par sample
dans le callback audio (thread-safe, pas d'allocation dynamique).

1. WOW & FLUTTER (irrégularité moteur)
   - Wow   : variation lente de vitesse (0.5–2 Hz), simule la déformation du disque
   - Flutter: variation rapide (4–15 Hz), simule le frottement de la tête de lecture
   Implémenté par ré-échantillonnage linéaire avec un index de lecture flottant.

2. CRÉPITEMENTS (crackle)
   - Générateur de clics aléatoires de forme exponentielle décroissante
   - Densité (clics/seconde), amplitude et durée réglables
   - Bruit de fond (hiss) continu léger

3. VITESSE MOTEUR (pitch shift global)
   - Facteur de vitesse global (0.5x = lent, 2.0x = rapide)
   - Change le pitch ET la durée (comme un vrai vinyle)
   - Combiné avec le wow/flutter
"""

from dataclasses import dataclass, field
import random
import numpy as np
import threading
from scipy.signal import lfilter


# ── Configuration ──────────────────────────────────────────────────────────────

@dataclass
class VinylConfig:
    enabled: bool = False

    # ── Vitesse moteur ──────────────────────────────────────────────────
    motor_speed: float = 1.0        # 0.5 = 33rpm simulé lent, 1.0 = normal, 2.0 = rapide

    # ── Wow (basse fréquence) ────────────────────────────────────────────
    wow_amount: float = 0.003       # amplitude de la déviation (0=off, 0.02=fort)
    wow_rate: float = 0.8           # Hz, fréquence d'oscillation (0.2–3)

    # ── Flutter (haute fréquence) ────────────────────────────────────────
    flutter_amount: float = 0.001   # amplitude (0=off, 0.01=fort)
    flutter_rate: float = 7.0       # Hz (3–20)

    # ── Aléatoire moteur (wow stochastique) ─────────────────────────────
    motor_random: float = 0.001     # perturbation brownienne de la vitesse (0=off, 0.01=fort)

    # ── Crépitements ────────────────────────────────────────────────────
    crackle_density: float = 30.0   # clics/seconde (0=silence, 200=très usé)
    crackle_amplitude: float = 0.08 # 0.0–1.0
    crackle_duration_ms: float = 3.0 # durée d'un clic en ms (1–20)

    # ── Bruit de fond (hiss) ────────────────────────────────────────────
    hiss_level: float = 0.004       # amplitude RMS du bruit blanc (0=off, 0.02=fort)


# ── Processeur ─────────────────────────────────────────────────────────────────

class VinylProcessor:
    """
    Applique l'effet vinyle sur un bloc stéréo float32 (N×2).
    Thread-safe : tout l'état est dans des attributs scalaires / numpy.
    """

    def __init__(self, sample_rate: int = 44100):
        self.config = VinylConfig()
        self._sr = sample_rate
        self._lock = threading.Lock()

        # ── État interne wow/flutter ──────────────────────────────────
        self._wow_phase = 0.0
        self._flutter_phase = 0.0
        self._read_index = 0.0          # index de lecture flottant (ré-échantillonnage)
        self._speed_random = 0.0        # composante brownienne courante
        self._previous_sample = np.zeros(2, dtype=np.float32)
        self._motor_rng = np.random.default_rng()
        self._noise_rng = np.random.default_rng()

        # ── Buffer de délai pour le ré-échantillonnage ─────────────────
        # On garde 2 samples précédents pour l'interpolation linéaire
        self._delay_buf = np.zeros((4, 2), dtype=np.float32)
        self._delay_pos = 0

        # ── État interne crépitements ─────────────────────────────────
        self._crackle_countdown = 0     # frames avant le prochain clic
        self._crackle_remaining = 0     # frames restantes du clic courant
        self._crackle_envelope = 0.0    # valeur courante de l'enveloppe
        self._crackle_decay = 0.0       # taux de décroissance par frame
        self._crackle_sign = 1.0        # polarité du clic (+1 ou -1)
        # RNG déterministe mais indépendant du reste
        self._rng = random.Random()
        self._next_crackle_countdown()

    def set_sample_rate(self, sr: int):
        with self._lock:
            self._sr = sr
            self._read_index = 0.0
            self._delay_buf[:] = 0
            self._previous_sample[:] = 0

    def reset_position(self):
        """Appeler lors d'un seek ou d'un chargement."""
        with self._lock:
            self._read_index = 0.0
            self._delay_buf[:] = 0
            self._previous_sample[:] = 0
            self._delay_pos = 0
            self._crackle_remaining = 0
            self._crackle_envelope = 0.0
            self._next_crackle_countdown()

    # ── Point d'entrée principal ──────────────────────────────────────

    def process(self, chunk: np.ndarray) -> np.ndarray:
        """
        chunk : ndarray float32 (N, 2) — modifié IN PLACE puis retourné.
        """
        if not self.config.enabled:
            return chunk

        with self._lock:
            cfg = self.config
            sr = self._sr

        out = self._apply_motor(chunk, cfg, sr)
        out = self._apply_crackle(out, cfg, sr)
        return out

    # ── Wow / Flutter / Vitesse (ré-échantillonnage) ─────────────────

    def _apply_motor(self, chunk: np.ndarray, cfg: VinylConfig, sr: int) -> np.ndarray:
        """
        Ré-échantillonnage avec vitesse variable.
        L'index de lecture avance de (motor_speed + wow + flutter + random) par frame.
        """
        n = len(chunk)
        if not n:
            return chunk
        out = np.zeros_like(chunk)
        wp = self._wow_phase
        fp = self._flutter_phase
        times = np.arange(n, dtype=np.float64) / sr
        wow = cfg.wow_amount * np.sin(2.0 * np.pi * cfg.wow_rate * (wp + times))
        flutter = cfg.flutter_amount * np.sin(
            2.0 * np.pi * cfg.flutter_rate * (fp + times)
        )

        increments = (
            self._motor_rng.random(n, dtype=np.float64) - 0.5
        ) * cfg.motor_random * 2.0
        random_walk, _ = lfilter(
            [0.995],
            [1.0, -0.995],
            increments,
            zi=[self._speed_random * 0.995],
        )
        random_walk = np.clip(random_walk, -0.05, 0.05)
        self._speed_random = float(random_walk[-1])

        speeds = np.maximum(0.1, cfg.motor_speed + wow + flutter + random_walk)
        positions = self._read_index + np.concatenate(
            (np.zeros(1, dtype=np.float64), np.cumsum(speeds[:-1]))
        )
        interpolation_positions = np.arange(-1, n + 1, dtype=np.float64)
        interpolation_samples = np.vstack(
            (self._previous_sample, chunk, chunk[-1])
        )
        for channel in range(chunk.shape[1]):
            out[:, channel] = np.interp(
                positions,
                interpolation_positions,
                interpolation_samples[:, channel],
            )

        # Wrap phases
        elapsed = n / sr
        self._wow_phase = (wp + elapsed) % (1.0 / max(cfg.wow_rate, 0.01))
        self._flutter_phase = (fp + elapsed) % (1.0 / max(cfg.flutter_rate, 0.01))
        self._read_index += float(np.sum(speeds)) - n
        self._previous_sample = chunk[-1].copy()

        return out

    # ── Crépitements / Hiss ───────────────────────────────────────────

    def _apply_crackle(self, chunk: np.ndarray, cfg: VinylConfig, sr: int) -> np.ndarray:
        n = len(chunk)
        out = chunk.copy()

        # Bruit de fond (hiss) : bruit blanc filtré passe-bas à ~8 kHz
        if cfg.hiss_level > 0:
            hiss = self._noise_rng.standard_normal(n).astype(np.float32)
            hiss *= cfg.hiss_level
            # Filtrage simple : moyenne mobile 3 points (adoucit le bruit)
            hiss[1:-1] = (hiss[:-2] + hiss[1:-1] + hiss[2:]) / 3.0
            out[:, 0] += hiss
            out[:, 1] += hiss * float(self._rng.random() * 0.3 + 0.85)  # légère variation L/R

        # Clics
        if cfg.crackle_amplitude > 0 and cfg.crackle_density > 0:
            i = 0
            while i < n:
                if self._crackle_remaining > 0:
                    count = min(self._crackle_remaining, n - i)
                    envelope = self._crackle_envelope * np.power(
                        self._crackle_decay, np.arange(count)
                    )
                    click = envelope * self._crackle_sign
                    right_gain = self._noise_rng.random(count) * 0.4 + 0.8
                    out[i:i + count, 0] += click
                    out[i:i + count, 1] += click * right_gain
                    self._crackle_envelope *= self._crackle_decay ** count
                    self._crackle_remaining -= count
                    i += count
                elif self._crackle_countdown <= 0:
                    # Déclencher un nouveau clic
                    dur_frames = max(1, int(cfg.crackle_duration_ms * sr / 1000.0))
                    self._crackle_remaining = dur_frames
                    # Decay pour atteindre ~1% à la fin
                    self._crackle_decay = (0.01 ** (1.0 / dur_frames))
                    self._crackle_envelope = cfg.crackle_amplitude * float(
                        self._rng.random() * 0.6 + 0.4  # amplitude variable 40–100%
                    )
                    self._crackle_sign = 1.0 if self._rng.random() > 0.5 else -1.0
                    self._next_crackle_countdown()
                else:
                    skipped = min(self._crackle_countdown, n - i)
                    self._crackle_countdown -= skipped
                    i += skipped

        return np.clip(out, -1.0, 1.0)

    def _next_crackle_countdown(self):
        """Calcule le nombre de frames jusqu'au prochain clic (distribution de Poisson)."""
        cfg = self.config
        sr = self._sr
        if cfg.crackle_density <= 0:
            self._crackle_countdown = sr * 10  # longtemps
            return
        # Distribution exponentielle : inter-arrivées d'un processus de Poisson
        mean_frames = sr / cfg.crackle_density
        # On tire une valeur exponentielle : -mean * ln(U)
        u = max(1e-9, float(self._rng.random()))
        self._crackle_countdown = max(1, int(-mean_frames * np.log(u)))
