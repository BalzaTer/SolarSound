"""
Logique principale du shuffle intelligent pour SolarSound.

Ce module contient :
- La sélection du premier morceau (>30s)
- Le calcul de compatibilité entre pistes
- La construction de l'ordre intelligent
"""

import random
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

try:
    from .smart_shuffle_config import SmartShuffleConfig, ShuffleMode
    from .custom_playlist import CustomTrack
    SMART_IMPORT_OK = True
except (ImportError, ModuleNotFoundError):
    SMART_IMPORT_OK = False


# Type alias pour les pistes (compatible avec CustomTrack et Track étendu)
TrackType = CustomTrack if SMART_IMPORT_OK else dict


def select_first_track(
    tracks: List[TrackType],
    config: SmartShuffleConfig,
    current_index: Optional[int] = None
) -> int:
    """
    Sélectionne le premier morceau pour le shuffle intelligent.
    
    Priorise les morceaux de durée >= first_track_min_duration.
    Utilise la méthode de sélection configurée (random, high_energy, low_energy, balanced).
    
    Args:
        tracks: Liste de toutes les pistes
        config: Configuration du shuffle intelligent
        current_index: Index de la piste actuelle (si en cours de lecture)
    
    Returns:
        Index de la piste choisie (-1 si aucune piste)
    """
    if not tracks:
        return -1

    # 1. Filtrer les pistes avec durée >= min_duration
    min_duration = config.first_track_min_duration
    valid_tracks = [
        (i, track) for i, track in enumerate(tracks)
        if hasattr(track, 'duration') and track.duration >= min_duration
    ]

    # 2. Si aucune piste ne satisfait la durée, prendre toutes les pistes
    if not valid_tracks:
        valid_tracks = list(enumerate(tracks))

    # 3. Appliquer la méthode de sélection
    method = config.first_track_selection

    if method == "random":
        # Sélection complètement aléatoire
        idx, _ = random.choice(valid_tracks)
        return idx

    elif method == "high_energy":
        # Sélectionner parmi les pistes avec énergie élevée
        high_energy_tracks = [
            (i, track) for i, track in valid_tracks
            if hasattr(track, 'avg_energy') and track.avg_energy and track.avg_energy >= 0.7
        ]
        if high_energy_tracks:
            idx, _ = random.choice(high_energy_tracks)
            return idx
        else:
            idx, _ = random.choice(valid_tracks)
            return idx

    elif method == "low_energy":
        # Sélectionner parmi les pistes avec énergie faible
        low_energy_tracks = [
            (i, track) for i, track in valid_tracks
            if hasattr(track, 'avg_energy') and track.avg_energy and track.avg_energy <= 0.3
        ]
        if low_energy_tracks:
            idx, _ = random.choice(low_energy_tracks)
            return idx
        else:
            idx, _ = random.choice(valid_tracks)
            return idx

    else:  # "balanced" (par défaut)
        # Sélection équilibrée : 30% haute énergie, 30% basse énergie, 40% aléatoire
        high_energy_tracks = [
            (i, track) for i, track in valid_tracks
            if hasattr(track, 'avg_energy') and track.avg_energy and track.avg_energy >= 0.7
        ]
        low_energy_tracks = [
            (i, track) for i, track in valid_tracks
            if hasattr(track, 'avg_energy') and track.avg_energy and track.avg_energy <= 0.3
        ]
        medium_energy_tracks = [
            (i, track) for i, track in valid_tracks
            if hasattr(track, 'avg_energy') and track.avg_energy and 0.3 < track.avg_energy < 0.7
        ]

        # Choisir une catégorie aléatoirement
        choice = random.random()
        if choice < 0.3 and high_energy_tracks:
            idx, _ = random.choice(high_energy_tracks)
            return idx
        elif choice < 0.6 and low_energy_tracks:
            idx, _ = random.choice(low_energy_tracks)
            return idx
        else:
            idx, _ = random.choice(valid_tracks)
            return idx


def get_track_bpm(track: TrackType) -> Optional[float]:
    """Récupère le BPM d'une piste, avec fallback sur avg_energy si nécessaire."""
    if hasattr(track, 'bpm') and track.bpm is not None:
        return track.bpm
    return None


def get_track_energy(track: TrackType, position: str = "avg") -> Optional[float]:
    """
    Récupère l'énergie d'une piste à une position donnée.
    
    Args:
        track: La piste
        position: "start", "end", ou "avg"
    
    Returns:
        Valeur d'énergie (0.0-1.0) ou None
    """
    if position == "start":
        if hasattr(track, 'start_energy') and track.start_energy is not None:
            return track.start_energy
        if hasattr(track, 'avg_energy') and track.avg_energy is not None:
            return track.avg_energy
    elif position == "end":
        if hasattr(track, 'end_energy') and track.end_energy is not None:
            return track.end_energy
        if hasattr(track, 'avg_energy') and track.avg_energy is not None:
            return track.avg_energy
    else:  # avg
        if hasattr(track, 'avg_energy') and track.avg_energy is not None:
            return track.avg_energy
        if hasattr(track, 'energy') and track.energy is not None:
            return track.energy
    return None


def get_track_volume(track: TrackType, position: str = "avg") -> Optional[float]:
    """
    Récupère le volume d'une piste à une position donnée.
    
    Args:
        track: La piste
        position: "start" ou "end"
    
    Returns:
        Valeur de volume (0.0-1.0) ou None
    """
    if position == "start":
        if hasattr(track, 'start_volume') and track.start_volume is not None:
            return track.start_volume
    elif position == "end":
        if hasattr(track, 'end_volume') and track.end_volume is not None:
            return track.end_volume
    return None


def compatibility_score(
    track_a: TrackType,
    track_b: TrackType,
    config: SmartShuffleConfig
) -> float:
    """
    Calcule le score de compatibilité entre deux pistes avec des poids configurables.
    
    Args:
        track_a: Piste actuelle (celle qui joue)
        track_b: Piste candidate (celle qui pourrait suivre)
        config: Configuration du shuffle intelligent
    
    Returns:
        Score de compatibilité (0-100)
    """
    score = 0.0
    total_weight = config.bpm_weight + config.energy_weight + config.volume_weight

    if total_weight == 0:
        return 50.0  # Score neutre si aucun poids

    # === 1. COMPATIBILITÉ BPM (poids configurable) ===
    bpm_a = get_track_bpm(track_a)
    bpm_b = get_track_bpm(track_b)
    
    if bpm_a is not None and bpm_b is not None:
        bpm_score = 0.0

        # Cas 1 : BPM proches
        bpm_diff = abs(bpm_a - bpm_b)
        if bpm_diff <= config.bpm_tolerance:
            bpm_score = 100.0
        elif bpm_diff <= config.bpm_tolerance * 2:
            bpm_score = 80.0
        elif bpm_diff <= config.bpm_tolerance * 3:
            bpm_score = 60.0
        elif bpm_diff <= config.bpm_tolerance * 4:
            bpm_score = 40.0
        else:
            bpm_score = 20.0

        # Cas 2 : BPM multiples (si activé)
        if config.enable_bpm_multiples:
            ratio = max(bpm_a / bpm_b, bpm_b / bpm_a)
            tolerance = config.bpm_multiple_ratio_tolerance

            if 2.0 - tolerance <= ratio <= 2.0 + tolerance:  # Multiple de 2
                bpm_score = max(bpm_score, 95.0)
            elif 3.0 - tolerance <= ratio <= 3.0 + tolerance:  # Multiple de 3
                bpm_score = max(bpm_score, 90.0)
            elif 1.5 - tolerance <= ratio <= 1.5 + tolerance:  # Multiple de 1.5
                bpm_score = max(bpm_score, 85.0)
            elif 0.5 - tolerance <= ratio <= 0.5 + tolerance:  # Moitié (ex: 160 → 80)
                bpm_score = max(bpm_score, 95.0)

        # Appliquer le poids BPM
        score += (bpm_score / 100.0) * config.bpm_weight

    # === 2. COMPATIBILITÉ ÉNERGIE (poids configurable) ===
    energy_a_end = get_track_energy(track_a, "end")
    energy_b_start = get_track_energy(track_b, "start")
    
    if energy_a_end is not None and energy_b_start is not None:
        energy_diff = abs(energy_a_end - energy_b_start)

        if energy_diff <= config.energy_tolerance:
            energy_score = 100.0
        elif energy_diff <= config.energy_tolerance * 2:
            energy_score = 80.0
        elif energy_diff <= config.energy_tolerance * 3:
            energy_score = 60.0
        elif energy_diff <= config.energy_tolerance * 4:
            energy_score = 40.0
        else:
            energy_score = 20.0

        # Appliquer le poids Énergie
        score += (energy_score / 100.0) * config.energy_weight

    # === 3. COMPATIBILITÉ VOLUME (poids configurable) ===
    volume_a_end = get_track_volume(track_a, "end")
    volume_b_start = get_track_volume(track_b, "start")
    
    if volume_a_end is not None and volume_b_start is not None:
        vol_diff = abs(volume_a_end - volume_b_start)

        if vol_diff <= config.volume_tolerance:
            volume_score = 100.0
        elif vol_diff <= config.volume_tolerance * 2:
            volume_score = 80.0
        elif vol_diff <= config.volume_tolerance * 3:
            volume_score = 60.0
        else:
            volume_score = 40.0

        # Appliquer le poids Volume
        score += (volume_score / 100.0) * config.volume_weight

    # Normaliser le score final (0-100)
    if total_weight > 0:
        score = (score / total_weight) * 100.0

    return min(100.0, max(0.0, score))


def build_smart_shuffle(
    tracks: List[TrackType],
    config: SmartShuffleConfig
) -> List[int]:
    """
    Construit un ordre de lecture optimisé pour le mode intelligent.
    
    Args:
        tracks: Liste de toutes les pistes
        config: Configuration du shuffle intelligent
    
    Returns:
        Liste d'index dans l'ordre de lecture
    """
    if not tracks:
        return []

    # 1. Sélectionner le premier morceau
    first_idx = select_first_track(tracks, config)
    if first_idx == -1:
        return []

    # 2. Initialiser l'ordre avec le premier morceau
    order = [first_idx]
    remaining = [i for i in range(len(tracks)) if i != first_idx]

    # 3. Construire le reste de l'ordre
    while remaining:
        last_idx = order[-1]
        last_track = tracks[last_idx]

        # Calculer les scores de compatibilité
        candidates = []
        for idx in remaining:
            candidate_track = tracks[idx]
            score = compatibility_score(last_track, candidate_track, config)
            candidates.append((idx, score))

        # Trier par score (descendant)
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Sélectionner la prochaine piste avec le facteur d'aléatoire
        chosen_idx = select_next_track_with_randomness(candidates, config)

        # Ajouter à l'ordre
        order.append(chosen_idx)
        remaining.remove(chosen_idx)

    return order


def select_next_track_with_randomness(
    candidates: List[Tuple[int, float]],
    config: SmartShuffleConfig
) -> int:
    """
    Sélectionne la prochaine piste en tenant compte du facteur d'aléatoire.
    
    Args:
        candidates: Liste de tuples (index, score)
        config: Configuration du shuffle intelligent
    
    Returns:
        Index de la piste choisie
    """
    if not candidates:
        return -1

    if config.randomness_factor == 0.0:
        # Mode déterministe : prendre le meilleur score
        return candidates[0][0]

    if config.randomness_factor == 1.0:
        # Mode aléatoire pur : choisir au hasard
        return random.choice(candidates)[0]

    # Mode mixte : pondération basée sur le score + aléatoire
    scores = [score for _, score in candidates]
    max_score = max(scores) if scores else 100.0

    # Calculer les poids en fonction du score et du facteur d'aléatoire
    weights = []
    for idx, score in candidates:
        # Normaliser le score (0-1)
        norm_score = score / max_score if max_score > 0 else 0.0

        # Appliquer le facteur d'aléatoire :
        #   poids = (1 - randomness) * norm_score + randomness * 0.5
        weight = (1.0 - config.randomness_factor) * norm_score + \
                 config.randomness_factor * 0.5

        # Assurer un poids minimal pour éviter l'exclusion
        weight = max(0.01, weight)
        weights.append(weight)

    # Normaliser les poids
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]

    # Choisir selon les poids
    chosen_idx, _ = random.choices(candidates, weights=weights, k=1)[0]
    return chosen_idx
