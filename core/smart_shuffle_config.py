"""Configuration du shuffle intelligent pour SolarSound."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class ShuffleMode(Enum):
    """Modes de shuffle disponibles."""
    SIMPLE = "simple"          # Aléatoire classique (déjà existant)
    INTELLIGENT = "intelligent"  # Nouveau mode intelligent


@dataclass
class SmartShuffleConfig:
    """
    Configuration du shuffle intelligent.
    
    Attributes:
        mode: Mode de shuffle (SIMPLE ou INTELLIGENT)
        bpm_weight: Poids du BPM (0-100)
        energy_weight: Poids de l'énergie (0-100)
        volume_weight: Poids du volume (0-100)
        bpm_tolerance: Tolérance pour "BPM proches" (±X BPM)
        enable_bpm_multiples: Autoriser les transitions 80→160, 100→200, etc.
        bpm_multiple_ratio_tolerance: Tolérance pour les multiples (ex: 1.9-2.1 pour ×2)
        energy_tolerance: Tolérance pour "énergie proche" (±X)
        min_energy_diff: Différence minimale d'énergie pour éviter les biais
        volume_tolerance: Tolérance pour "volume proche" (±X)
        first_track_min_duration: Durée minimale en secondes pour le premier morceau
        first_track_selection: Méthode de sélection du premier morceau
        randomness_factor: 0.0 = déterministe, 1.0 = aléatoire pur
        enable_cache: Activer le cache des scores de compatibilité
        max_tracks_for_smart_mode: Limite pour le mode intelligent
    """
    
    # --- Mode principal ---
    mode: ShuffleMode = ShuffleMode.SIMPLE
    
    # --- Poids des critères (0-100, somme = 100) ---
    bpm_weight: int = 50
    energy_weight: int = 30
    volume_weight: int = 20
    
    # --- Paramètres BPM ---
    bpm_tolerance: float = 5.0
    enable_bpm_multiples: bool = True
    bpm_multiple_ratio_tolerance: float = 0.1
    
    # --- Paramètres Énergie ---
    energy_tolerance: float = 0.1
    min_energy_diff: float = 0.0
    
    # --- Paramètres Volume ---
    volume_tolerance: float = 0.1
    
    # --- Sélection du premier morceau ---
    first_track_min_duration: float = 30.0
    first_track_selection: str = "balanced"  # "random", "high_energy", "low_energy", "balanced"
    
    # --- Aléatoire contrôlé ---
    randomness_factor: float = 0.3
    
    # --- Cache et performances ---
    enable_cache: bool = True
    max_tracks_for_smart_mode: int = 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour la sauvegarde."""
        return {
            "mode": self.mode.value,
            "bpm_weight": self.bpm_weight,
            "energy_weight": self.energy_weight,
            "volume_weight": self.volume_weight,
            "bpm_tolerance": self.bpm_tolerance,
            "enable_bpm_multiples": self.enable_bpm_multiples,
            "bpm_multiple_ratio_tolerance": self.bpm_multiple_ratio_tolerance,
            "energy_tolerance": self.energy_tolerance,
            "min_energy_diff": self.min_energy_diff,
            "volume_tolerance": self.volume_tolerance,
            "first_track_min_duration": self.first_track_min_duration,
            "first_track_selection": self.first_track_selection,
            "randomness_factor": self.randomness_factor,
            "enable_cache": self.enable_cache,
            "max_tracks_for_smart_mode": self.max_tracks_for_smart_mode,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SmartShuffleConfig":
        """Crée depuis un dictionnaire."""
        config = cls()
        for key, value in data.items():
            if hasattr(config, key):
                if key == "mode" and isinstance(value, str):
                    try:
                        setattr(config, key, ShuffleMode(value))
                    except ValueError:
                        setattr(config, key, ShuffleMode.SIMPLE)
                else:
                    setattr(config, key, value)
        return config
    
    @classmethod
    def default(cls) -> "SmartShuffleConfig":
        """Retourne la configuration par défaut."""
        return cls()
    
    def validate(self) -> bool:
        """Valide la configuration."""
        if not (0 <= self.bpm_weight <= 100):
            return False
        if not (0 <= self.energy_weight <= 100):
            return False
        if not (0 <= self.volume_weight <= 100):
            return False
        if self.bpm_weight + self.energy_weight + self.volume_weight != 100:
            return False
        if not (0 <= self.randomness_factor <= 1.0):
            return False
        if self.first_track_min_duration < 0:
            return False
        if self.max_tracks_for_smart_mode < 1:
            return False
        return True
    
    def normalize_weights(self):
        """Normalise les poids pour que leur somme fasse 100."""
        total = self.bpm_weight + self.energy_weight + self.volume_weight
        if total == 0:
            self.bpm_weight = 50
            self.energy_weight = 30
            self.volume_weight = 20
        else:
            self.bpm_weight = int((self.bpm_weight / total) * 100)
            self.energy_weight = int((self.energy_weight / total) * 100)
            self.volume_weight = 100 - self.bpm_weight - self.energy_weight
