"""Extraction de métadonnées audio pour transitions harmonieuses"""

import os
from typing import Optional, Dict

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, ID3NoHeaderError
    from mutagen import File as MutagenFile
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False


def extract_audio_metadata(filepath: str) -> Dict[str, object]:
    """
    Extrait les métadonnées audio d'un fichier.
    
    Retourne un dictionnaire avec :
    - bpm: float ou None (battements par minute)
    - key: str ou None (tonalité, ex: "C", "D#", "Am")
    - energy: float 0.0-1.0 ou None (niveau d'énergie estimé)
    - genre: str ou None (genre musical)
    - duration: float (en secondes)
    
    N'exclut JAMAIS les pistes : si métadonnée manquante, retourne None pour ce champ.
    
    Args:
        filepath: Chemin du fichier audio
        
    Returns:
        Dict avec clés {bpm, key, energy, genre, duration}
    """
    result = {
        "bpm": None,
        "key": None,
        "energy": None,
        "genre": None,
        "duration": 0.0,
    }

    if not filepath or not os.path.exists(filepath):
        return result

    if not MUTAGEN_OK:
        return result

    try:
        # Charger le fichier avec Mutagen (support multi-format)
        audio_file = MutagenFile(filepath)
        if not audio_file:
            return result

        # Durée
        if hasattr(audio_file.info, 'length'):
            result["duration"] = float(audio_file.info.length)

        # Métadonnées ID3 (MP3 et formats supportant ID3)
        try:
            id3 = ID3(filepath)
            
            # BPM (frame TBPM)
            bpm = id3.getall("TBPM")
            if bpm and len(bpm) > 0:
                try:
                    result["bpm"] = float(str(bpm[0]))
                except (ValueError, TypeError):
                    pass

            # Tonalité (frame TKEY)
            key = id3.getall("TKEY")
            if key and len(key) > 0:
                result["key"] = str(key[0])

            # Genre (frame TCON)
            genre = id3.getall("TCON")
            if genre and len(genre) > 0:
                result["genre"] = str(genre[0])

        except ID3NoHeaderError:
            # Pas de tags ID3, continuer
            pass

        # Métadonnées Vorbis (FLAC, OGG, etc.)
        if hasattr(audio_file, 'tags') and audio_file.tags:
            tags = audio_file.tags
            
            # BPM
            if "BPM" in tags and result["bpm"] is None:
                try:
                    result["bpm"] = float(tags["BPM"][0])
                except (ValueError, TypeError, IndexError):
                    pass

            # Tonalité / Key
            for key_name in ["KEY", "INITIALKEY"]:
                if key_name in tags and result["key"] is None:
                    result["key"] = str(tags[key_name][0])
                    break

            # Genre
            if "GENRE" in tags and result["genre"] is None:
                result["genre"] = str(tags["GENRE"][0])

        # Estimer énergie à partir du BPM et de la durée (heuristique simple)
        if result["bpm"] and result["duration"]:
            result["energy"] = _estimate_energy(result["bpm"], result["duration"])

    except Exception as e:
        print(f"[audio_analysis] Erreur extraction {filepath}: {e}")

    return result


def _estimate_energy(bpm: float, duration: float) -> float:
    """
    Estime le niveau d'énergie d'une piste (0.0-1.0).
    
    Basée sur le BPM et la durée.
    - Ballades : 0.0-0.3 (< 80 BPM)
    - Modéré : 0.3-0.6 (80-130 BPM)
    - Énergique : 0.6-1.0 (> 130 BPM)
    
    Args:
        bpm: Battements par minute
        duration: Durée en secondes (peu d'influence)
        
    Returns:
        Float 0.0-1.0
    """
    # Limiter BPM entre 40 et 200
    bpm = max(40, min(200, bpm))

    # Transformation : 40 BPM → 0.0, 200 BPM → 1.0
    energy = (bpm - 40) / 160

    return max(0.0, min(1.0, energy))


def get_all_audio_metadata(file_paths: list) -> dict:
    """
    Extrait les métadonnées pour une liste de fichiers.
    
    Args:
        file_paths: Liste de chemins fichiers
        
    Returns:
        Dict {filepath: metadata_dict}
    """
    result = {}
    for path in file_paths:
        result[path] = extract_audio_metadata(path)
    return result
