"""
Analyse des transitions audio pour le shuffle intelligent.

Ce module permet d'extraire :
- start_energy / end_energy (niveau d'intensité au début/fin)
- start_volume / end_volume (niveau sonore au début/fin)
- bpm (si non présent dans les tags)

Utilise librosa pour l'analyse audio.
"""

import os
import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Gestion des dépendances optionnelles
LIBROSA_AVAILABLE = False
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    pass

# Chemin du cache par défaut
DEFAULT_CACHE_DIR = os.path.expanduser("~/.solarsound")
TRANSITION_CACHE_FILE = "transition_cache.json"


class TransitionAnalysisError(Exception):
    """Erreur lors de l'analyse des transitions."""
    pass


def ensure_cache_dir(cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """S'assure que le répertoire de cache existe."""
    path = Path(cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_cache_path(cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """Retourne le chemin du fichier de cache."""
    ensure_cache_dir(cache_dir)
    return os.path.join(cache_dir, TRANSITION_CACHE_FILE)


def load_transition_cache(cache_dir: str = DEFAULT_CACHE_DIR) -> Dict[str, Dict]:
    """Charge le cache des analyses de transitions."""
    cache_path = get_cache_path(cache_dir)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_transition_cache(cache: Dict[str, Dict], cache_dir: str = DEFAULT_CACHE_DIR) -> bool:
    """Sauvegarde le cache des analyses de transitions."""
    cache_path = get_cache_path(cache_dir)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        return True
    except IOError:
        return False


def clear_transition_cache(cache_dir: str = DEFAULT_CACHE_DIR) -> bool:
    """Efface le cache des analyses de transitions."""
    cache_path = get_cache_path(cache_dir)
    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
            return True
        except IOError:
            return False
    return True


def _normalize_audio(y: np.ndarray) -> np.ndarray:
    """Normalise le signal audio entre -1 et 1."""
    if np.max(np.abs(y)) > 0:
        return y / np.max(np.abs(y))
    return y


def _calculate_rms(y: np.ndarray) -> float:
    """Calcule la valeur RMS (Root Mean Square) d'un signal."""
    return float(np.sqrt(np.mean(y ** 2)))


def _calculate_energy_from_mfcc(y: np.ndarray, sr: int, n_mfcc: int = 13) -> float:
    """
    Estime l'énergie à partir des coefficients MFCC.
    
    Args:
        y: Signal audio
        sr: Taux d'échantillonnage
        n_mfcc: Nombre de coefficients MFCC
    
    Returns:
        Valeur d'énergie normalisée (0.0-1.0)
    """
    try:
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
        # Moyenne des coefficients (plus représentative que le RMS seul)
        energy = float(np.mean(mfcc))
        # Normalisation empirique (les MFCC sont généralement entre -10 et 10)
        return max(0.0, min(1.0, (energy + 10) / 20))
    except Exception:
        return 0.5  # Valeur par défaut


def _estimate_bpm(y: np.ndarray, sr: int) -> Optional[float]:
    """
    Estime le BPM d'un extrait audio.
    
    Args:
        y: Signal audio
        sr: Taux d'échantillonnage
    
    Returns:
        BPM estimé ou None si échec
    """
    try:
        # Utiliser un extrait plus long pour une meilleure estimation
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo)
        # Valider le BPM (entre 40 et 200 pour éviter les aberrations)
        if 40 <= bpm <= 200:
            return round(bpm, 1)
        return None
    except Exception:
        return None


def analyze_track_transitions(
    filepath: str,
    duration: float = 30.0,
    cache_dir: str = DEFAULT_CACHE_DIR,
    use_cache: bool = True
) -> Dict[str, Optional[float]]:
    """
    Analyse une piste pour extraire les métadonnées de transition.
    
    Args:
        filepath: Chemin du fichier audio
        duration: Durée maximale à analyser (en secondes)
        cache_dir: Répertoire du cache
        use_cache: Utiliser le cache si disponible
    
    Returns:
        Dictionnaire avec les clés :
        - start_energy (0.0-1.0)
        - end_energy (0.0-1.0)
        - start_volume (0.0-1.0)
        - end_volume (0.0-1.0)
        - bpm (float ou None)
    
    Raises:
        TransitionAnalysisError: Si l'analyse échoue
    """
    if not LIBROSA_AVAILABLE:
        raise TransitionAnalysisError(
            "librosa est requis pour l'analyse des transitions. "
            "Installez-le avec : pip install librosa"
        )
    
    if not os.path.exists(filepath):
        raise TransitionAnalysisError(f"Fichier introuvable : {filepath}")

    # 1. Vérifier le cache
    if use_cache:
        cache = load_transition_cache(cache_dir)
        cache_key = os.path.abspath(filepath)
        if cache_key in cache:
            return cache[cache_key]

    result = {
        "start_energy": None,
        "end_energy": None,
        "start_volume": None,
        "end_volume": None,
        "bpm": None,
    }

    try:
        # 2. Charger le fichier audio
        y, sr = librosa.load(filepath, sr=22050, duration=duration, mono=True)
        
        if len(y) == 0:
            raise TransitionAnalysisError("Fichier audio vide ou non valide")

        # Normaliser le signal
        y = _normalize_audio(y)

        # 3. Extraire les segments début et fin
        segment_duration = 5.0  # 5 secondes pour chaque segment
        
        # Segment début
        start_samples = int(segment_duration * sr)
        if len(y) >= start_samples:
            start_segment = y[:start_samples]
        else:
            start_segment = y
        
        # Segment fin
        end_samples = int(segment_duration * sr)
        if len(y) >= end_samples:
            end_segment = y[-end_samples:]
        else:
            end_segment = y

        # 4. Calculer les métadonnées
        
        # BPM (sur tout le signal)
        result["bpm"] = _estimate_bpm(y, sr)

        # Start energy (à partir des MFCC)
        result["start_energy"] = _calculate_energy_from_mfcc(start_segment, sr)
        
        # End energy
        result["end_energy"] = _calculate_energy_from_mfcc(end_segment, sr)

        # Start volume (RMS normalisé)
        start_rms = _calculate_rms(start_segment)
        result["start_volume"] = float(np.clip(start_rms, 0.0, 1.0))
        
        # End volume
        end_rms = _calculate_rms(end_segment)
        result["end_volume"] = float(np.clip(end_rms, 0.0, 1.0))

    except Exception as e:
        raise TransitionAnalysisError(f"Erreur lors de l'analyse de {filepath}: {e}")

    # 5. Sauvegarder dans le cache
    if use_cache:
        cache = load_transition_cache(cache_dir)
        cache[os.path.abspath(filepath)] = result
        save_transition_cache(cache, cache_dir)

    return result


def analyze_tracks_transitions(
    filepaths: List[str],
    duration: float = 30.0,
    cache_dir: str = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    max_failures: int = 5
) -> Dict[str, Dict[str, Optional[float]]]:
    """
    Analyse plusieurs pistes pour extraire les métadonnées de transition.
    
    Args:
        filepaths: Liste des chemins de fichiers
        duration: Durée maximale à analyser (en secondes)
        cache_dir: Répertoire du cache
        use_cache: Utiliser le cache si disponible
        max_failures: Nombre maximum d'échecs avant d'arrêter
    
    Returns:
        Dictionnaire {filepath: result_dict}
    """
    results = {}
    failures = 0
    
    for filepath in filepaths:
        try:
            results[filepath] = analyze_track_transitions(
                filepath, duration, cache_dir, use_cache
            )
        except TransitionAnalysisError as e:
            print(f"[transition_analysis] Échec pour {filepath}: {e}")
            results[filepath] = {
                "start_energy": None,
                "end_energy": None,
                "start_volume": None,
                "end_volume": None,
                "bpm": None,
            }
            failures += 1
            if failures >= max_failures:
                print(f"[transition_analysis] Arrêt après {max_failures} échecs")
                break
    
    return results


def get_track_transition_metadata(
    track: object,
    filepath: Optional[str] = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
    use_cache: bool = True
) -> Dict[str, Optional[float]]:
    """
    Récupère ou calcule les métadonnées de transition pour une piste.
    
    Args:
        track: Objet piste (doit avoir un attribut 'path')
        filepath: Chemin du fichier (optionnel, sinon utilise track.path)
        cache_dir: Répertoire du cache
        use_cache: Utiliser le cache si disponible
    
    Returns:
        Dictionnaire avec les métadonnées de transition
    """
    if filepath is None:
        if hasattr(track, 'path'):
            filepath = track.path
        else:
            return {
                "start_energy": None,
                "end_energy": None,
                "start_volume": None,
                "end_volume": None,
                "bpm": None,
            }
    
    if not os.path.exists(filepath):
        return {
            "start_energy": None,
            "end_energy": None,
            "start_volume": None,
            "end_volume": None,
            "bpm": None,
        }
    
    try:
        return analyze_track_transitions(filepath, cache_dir=cache_dir, use_cache=use_cache)
    except TransitionAnalysisError:
        return {
            "start_energy": None,
            "end_energy": None,
            "start_volume": None,
            "end_volume": None,
            "bpm": None,
        }


def update_track_with_transitions(
    track: object,
    cache_dir: str = DEFAULT_CACHE_DIR,
    use_cache: bool = True
) -> object:
    """
    Met à jour une piste avec ses métadonnées de transition.
    
    Args:
        track: Objet piste (doit avoir des attributs path, start_energy, etc.)
        cache_dir: Répertoire du cache
        use_cache: Utiliser le cache si disponible
    
    Returns:
        La piste mise à jour
    """
    if not hasattr(track, 'path'):
        return track
    
    metadata = get_track_transition_metadata(track, cache_dir=cache_dir, use_cache=use_cache)
    
    # Mettre à jour les attributs de la piste
    if hasattr(track, 'start_energy') and metadata.get('start_energy') is not None:
        track.start_energy = metadata['start_energy']
    if hasattr(track, 'end_energy') and metadata.get('end_energy') is not None:
        track.end_energy = metadata['end_energy']
    if hasattr(track, 'start_volume') and metadata.get('start_volume') is not None:
        track.start_volume = metadata['start_volume']
    if hasattr(track, 'end_volume') and metadata.get('end_volume') is not None:
        track.end_volume = metadata['end_volume']
    if hasattr(track, 'bpm') and metadata.get('bpm') is not None:
        if track.bpm is None:  # Ne pas écraser un BPM existant
            track.bpm = metadata['bpm']
    
    return track
