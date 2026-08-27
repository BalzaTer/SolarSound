"""Lecture des métadonnées audio (ID3, RIFF INFO, Vorbis et MP4)."""

import os
from typing import Optional

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3NoHeaderError, ID3, APIC
    from mutagen import File as MutagenFile
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False

try:
    import wave
    WAVE_OK = True
except ImportError:
    WAVE_OK = False


def read_metadata(filepath: str) -> dict:
    """
    Retourne un dictionnaire avec :
      title, artist, album, duration (float, secondes)
    """
    result = {
        "title": os.path.splitext(os.path.basename(filepath))[0],
        "artist": "",
        "album": "",
        "duration": 0.0,
    }
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".wav":
        _read_wav(filepath, result)
    if MUTAGEN_OK:
        # Les tags WAV sont complétés par Mutagen après la durée RIFF.
        _read_mutagen(filepath, result)

    return result


def read_cover_art_data(filepath: str) -> Optional[bytes]:
    """Retourne les octets d’une pochette, depuis les tags ou un fichier image voisin."""
    if not filepath or not os.path.exists(filepath):
        return None

    embedded = _read_embedded_cover_art(filepath)
    if embedded:
        return embedded

    return _find_sidecar_cover_art(filepath)


def _read_embedded_cover_art(filepath: str) -> Optional[bytes]:
    if not MUTAGEN_OK:
        return None

    try:
        audio = MutagenFile(filepath, easy=False)
        if audio is None:
            return None

        tags = getattr(audio, "tags", None)
        if not tags:
            return None

        if isinstance(tags, ID3):
            for frame in tags.getall("APIC"):
                data = getattr(frame, "data", None)
                if data:
                    return bytes(data)

        for key in ("covr", "APIC", "metadata_block_pic"):
            try:
                values = tags.getall(key)
            except Exception:
                continue
            for value in values:
                if hasattr(value, "data") and value.data:
                    return bytes(value.data)
                if isinstance(value, (bytes, bytearray)) and value:
                    return bytes(value)
    except Exception:
        return None

    return None


def _find_sidecar_cover_art(filepath: str) -> Optional[bytes]:
    directory = os.path.dirname(filepath) or "."
    if not os.path.isdir(directory):
        return None

    base_name = os.path.splitext(os.path.basename(filepath))[0].lower()
    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
    candidates = []

    for entry in os.listdir(directory):
        full_path = os.path.join(directory, entry)
        if not os.path.isfile(full_path):
            continue
        ext = os.path.splitext(entry)[1].lower()
        if ext not in image_exts:
            continue
        lowered = entry.lower()
        if any(token in lowered for token in ("cover", "folder", "front", "album", "art")) or base_name in lowered:
            candidates.append(full_path)

    if not candidates:
        return None

    candidates.sort(key=lambda p: (
        not any(token in os.path.basename(p).lower() for token in ("cover", "folder", "front", "album", "art")),
        os.path.basename(p).lower(),
    ))

    for candidate in candidates:
        try:
            with open(candidate, "rb") as handle:
                data = handle.read()
            if data:
                return data
        except Exception:
            continue
    return None


def _read_mp3(filepath: str, result: dict):
    _read_mutagen(filepath, result)


def _read_mutagen(filepath: str, result: dict):
    """Lit les tags communs de tous les formats reconnus par Mutagen."""
    if not MUTAGEN_OK:
        return
    try:
        audio = MutagenFile(filepath, easy=True)
        if audio is None:
            return
        result["duration"] = audio.info.length if hasattr(audio, "info") else 0.0
        for field in ("title", "artist", "album"):
            value = audio.get(field)
            if value:
                result[field] = str(value[0] if isinstance(value, (list, tuple)) else value)
    except Exception:
        pass


def _read_wav(filepath: str, result: dict):
    if not WAVE_OK:
        return
    try:
        import wave as wv
        with wv.open(filepath, "rb") as f:
            frames = f.getnframes()
            rate = f.getframerate()
            result["duration"] = frames / rate if rate else 0.0
    except Exception:
        pass

    # Essayer mutagen pour les tags WAV
    if MUTAGEN_OK:
        try:
            audio = MutagenFile(filepath, easy=True)
            if audio and hasattr(audio, "tags") and audio.tags:
                t = audio.tags
                if t.get("title"):
                    result["title"] = str(t["title"][0])
                if t.get("artist"):
                    result["artist"] = str(t["artist"][0])
                if t.get("album"):
                    result["album"] = str(t["album"][0])
        except Exception:
            pass


def format_duration(seconds: float) -> str:
    """Formate des secondes en mm:ss ou h:mm:ss"""
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    s = s % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
