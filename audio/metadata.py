"""Lecture des métadonnées audio (ID3, RIFF INFO)"""

import os
from typing import Optional

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3NoHeaderError
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
    ext = filepath.lower().rsplit(".", 1)[-1]

    if ext == "wav":
        _read_wav(filepath, result)
    elif ext == "mp3":
        _read_mp3(filepath, result)

    return result


def _read_mp3(filepath: str, result: dict):
    if not MUTAGEN_OK:
        return
    try:
        audio = MutagenFile(filepath, easy=True)
        if audio is None:
            return
        result["duration"] = audio.info.length if hasattr(audio, "info") else 0.0
        if audio.get("title"):
            result["title"] = str(audio["title"][0])
        if audio.get("artist"):
            result["artist"] = str(audio["artist"][0])
        if audio.get("album"):
            result["album"] = str(audio["album"][0])
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
