"""
Indexation des dossiers de musique locaux configurés par l'utilisateur.

Sert à deux choses :
1. Élargir la recherche de la barre du haut aux fichiers audio présents sur
   le disque mais pas encore ajoutés à une playlist.
2. Retrouver les pistes de playlists personnalisées dont le fichier a été
   déplacé ou renommé, en se basant sur la taille du fichier et les
   métadonnées plutôt que sur le chemin d'origine.
"""

import os
from typing import List, Optional

try:
    from .playlist import Playlist
    from ..audio.metadata import read_metadata
except (ImportError, ModuleNotFoundError):
    from core.playlist import Playlist
    from audio.metadata import read_metadata


def scan_library_folders(folders: List[str], report=None) -> List[dict]:
    """
    Parcourt récursivement les dossiers fournis et retourne les fichiers
    audio trouvés, avec métadonnées de base et taille de fichier.

    Args:
        report: callback optionnel `report(current, total, message)` pour
                suivre la progression (voir ui/progress_dialog.py)

    Chaque entrée : {path, size, title, artist, album, duration}
    """
    supported = set(Playlist.SUPPORTED_FORMATS)

    # 1er passage (rapide) : lister les fichiers à traiter, sans lire les tags
    all_paths = []
    seen_paths = set()
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        for root, _, files in os.walk(folder):
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in supported:
                    continue
                path = os.path.join(root, name)
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                all_paths.append(path)

    total = len(all_paths)
    if report:
        report(0, total, f"{total} fichier(s) trouvé(s), analyse des métadonnées…")

    entries = []
    for i, path in enumerate(all_paths, start=1):
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        info = read_metadata(path)
        entries.append({
            "path": path,
            "size": size,
            "title": info.get("title", ""),
            "artist": info.get("artist", ""),
            "album": info.get("album", ""),
            "duration": info.get("duration", 0.0),
        })
        if report and (i % 5 == 0 or i == total):
            report(i, total, f"Analyse des métadonnées… ({i}/{total}) {os.path.basename(path)}")

    return entries


def find_replacement_for_track(track, library_index: List[dict]) -> Optional[dict]:
    """
    Cherche, parmi les fichiers indexés, celui qui correspond le mieux à une
    piste dont le fichier d'origine n'existe plus (déplacé/renommé).

    Stratégie (du plus fiable au moins fiable) :
    1. Taille de fichier identique (mémorisée sur la piste à l'ajout) et
       durée proche (± 2 secondes) -> correspondance quasi certaine, robuste
       même si le fichier a été renommé et déplacé n'importe où.
    2. Titre + artiste identiques (métadonnées) -> repli utile si la taille
       n'est pas connue (anciennes playlists) ou si le fichier a été
       ré-encodé (taille différente mais mêmes tags).

    Returns:
        L'entrée d'index correspondante, ou None si rien de suffisamment
        fiable n'a été trouvé.
    """
    track_title = (getattr(track, "title", "") or "").strip().lower()
    track_artist = (getattr(track, "artist", "") or "").strip().lower()
    track_duration = getattr(track, "duration", 0.0) or 0.0
    track_size = getattr(track, "file_size", None)

    if track_size:
        for entry in library_index:
            if entry["size"] == track_size:
                if track_duration <= 0 or abs(entry.get("duration", 0.0) - track_duration) <= 2.0:
                    return entry

    if track_title:
        for entry in library_index:
            if (entry.get("title", "").strip().lower() == track_title
                    and (not track_artist or entry.get("artist", "").strip().lower() == track_artist)):
                return entry

    return None
