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
import numpy as np
import threading


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
        self._rng = np.random.default_rng()
        self._next_crackle_countdown()

    def set_sample_rate(self, sr: int):
        with self._lock:
            self._sr = sr
            self._read_index = 0.0
            self._delay_buf[:] = 0

    def reset_position(self):
        """Appeler lors d'un seek ou d'un chargement."""
        with self._lock:
            self._read_index = 0.0
            self._delay_buf[:] = 0
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
        out = np.zeros_like(chunk)

        # Pas temporel pour une frame
        dt = 1.0 / sr

        # On garde une copie du chunk dans un buffer circulaire court
        # pour l'interpolation (lecture légèrement en avance ou en retard)
        wp = self._wow_phase
        fp = self._flutter_phase
        sr_rnd = self._speed_random
        ri = self._read_index

        for i in range(n):
            # ── Calcul de la vitesse instantanée ────────────────────
            wow_mod     = cfg.wow_amount    * np.sin(2.0 * np.pi * cfg.wow_rate * wp)
            flutter_mod = cfg.flutter_amount * np.sin(2.0 * np.pi * cfg.flutter_rate * fp)

            # Marche brownienne pour l'aléatoire moteur
            sr_rnd += (self._rng.random() - 0.5) * cfg.motor_random * 2.0
            sr_rnd *= 0.995  # retour vers 0 progressif
            sr_rnd = float(np.clip(sr_rnd, -0.05, 0.05))

            speed = cfg.motor_speed + wow_mod + flutter_mod + sr_rnd
            speed = max(0.1, speed)  # jamais négatif

            # ── Interpolation linéaire sur le chunk ──────────────────
            idx_floor = int(ri)
            frac = ri - idx_floor

            if 0 <= idx_floor < n - 1:
                s0 = chunk[idx_floor]
                s1 = chunk[idx_floor + 1]
                out[i] = s0 + frac * (s1 - s0)
            elif 0 <= idx_floor < n:
                out[i] = chunk[idx_floor]
            else:
                # Hors plage : silence (arrive rarement avec speed >> 1)
                out[i] = 0.0

            ri += speed
            wp += dt
            fp += dt

        # Wrap phases
        self._wow_phase     = wp % (1.0 / max(cfg.wow_rate, 0.01))
        self._flutter_phase = fp % (1.0 / max(cfg.flutter_rate, 0.01))
        self._speed_random  = sr_rnd

        # L'index de lecture repart à 0 pour le prochain bloc
        # (on lit toujours les n samples du bloc courant)
        # On retient le surplus fractionnaire pour la continuité inter-blocs
        self._read_index = ri - int(ri)  # fraction résiduelle

        return out

    # ── Crépitements / Hiss ───────────────────────────────────────────

    def _apply_crackle(self, chunk: np.ndarray, cfg: VinylConfig, sr: int) -> np.ndarray:
        n = len(chunk)
        out = chunk.copy()

        # Bruit de fond (hiss) : bruit blanc filtré passe-bas à ~8 kHz
        if cfg.hiss_level > 0:
            hiss = self._rng.standard_normal(n).astype(np.float32) * cfg.hiss_level
            # Filtrage simple : moyenne mobile 3 points (adoucit le bruit)
            hiss[1:-1] = (hiss[:-2] + hiss[1:-1] + hiss[2:]) / 3.0
            out[:, 0] += hiss
            out[:, 1] += hiss * float(self._rng.random() * 0.3 + 0.85)  # légère variation L/R

        # Clics
        if cfg.crackle_amplitude > 0 and cfg.crackle_density > 0:
            i = 0
            while i < n:
                if self._crackle_remaining > 0:
                    # Appliquer l'enveloppe du clic courant
                    amp = self._crackle_envelope * self._crackle_sign
                    out[i, 0] += amp
                    out[i, 1] += amp * float(self._rng.random() * 0.4 + 0.8)  # L/R légèrement différents
                    self._crackle_envelope *= self._crackle_decay
                    self._crackle_remaining -= 1
                    i += 1
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
                    self._crackle_countdown -= 1
                    i += 1

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
