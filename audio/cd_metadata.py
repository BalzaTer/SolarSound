"""
Récupération automatique des métadonnées d'un CD audio (titre, artiste,
album, pochette) à partir du sommaire du disque (TOC), via la base de
données publique et gratuite MusicBrainz + Cover Art Archive.

Aucune dépendance supplémentaire : utilise uniquement la bibliothèque
standard (urllib), pas de clé API requise.
"""

import json
import urllib.request
import urllib.parse
from typing import Optional, List


MB_API_URL = "https://musicbrainz.org/ws/2/discid/-"
COVER_ART_URL = "https://coverartarchive.org/release/{mbid}/front-500"

# MusicBrainz impose un en-tête User-Agent identifiant l'application
# (obligatoire, sous peine de blocage des requêtes). Personnalisez cette
# valeur si vous distribuez l'application sous un autre nom/contact.
USER_AGENT = "SolarSound-MusicPlayer/1.0 ( https://github.com/solarsound/solarsound )"


def build_toc_string(first_track: int, last_track: int, leadout_offset: int,
                      track_offsets: List[int]) -> str:
    """Construit le paramètre TOC attendu par MusicBrainz (format CDDB/freedb)."""
    parts = [str(first_track), str(last_track), str(leadout_offset)]
    parts.extend(str(o) for o in track_offsets)
    return " ".join(parts)


def fetch_release_by_toc(toc: dict, timeout: float = 8.0) -> Optional[dict]:
    """
    Interroge MusicBrainz avec le TOC d'un disque et retourne la première
    correspondance, ou None si aucune correspondance / pas de réseau.

    Args:
        toc: dict avec les clés first_track, last_track, leadout_offset,
             track_offsets (voir CdAudio.read_toc)

    Returns:
        dict avec les clés : mbid, album, artist, year, tracks (liste de
        titres dans l'ordre des pistes), ou None si rien trouvé/erreur
    """
    try:
        toc_str = build_toc_string(
            toc["first_track"], toc["last_track"],
            toc["leadout_offset"], toc["track_offsets"],
        )
    except (KeyError, TypeError):
        return None

    query = urllib.parse.urlencode({
        "toc": toc_str,
        "fmt": "json",
        "inc": "recordings+artist-credits",
    })
    url = f"{MB_API_URL}?{query}"

    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[CdMetadata] Recherche MusicBrainz impossible : {e}")
        return None

    releases = data.get("releases") or []
    if not releases:
        return None

    release = releases[0]
    mbid = release.get("id")
    album = release.get("title", "") or ""

    artist = ""
    credits = release.get("artist-credit") or []
    if credits:
        artist = credits[0].get("name") or (credits[0].get("artist") or {}).get("name", "")

    year = (release.get("date") or "")[:4]

    tracks = []
    media = release.get("media") or []
    if media:
        for t in media[0].get("tracks", []):
            tracks.append(t.get("title", "") or "")

    return {
        "mbid": mbid,
        "album": album,
        "artist": artist,
        "year": year,
        "tracks": tracks,
    }


def fetch_cover_art(mbid: str, timeout: float = 8.0) -> Optional[bytes]:
    """
    Récupère la pochette d'une release MusicBrainz via Cover Art Archive.
    Retourne None si aucune pochette n'est disponible (cas normal, pas
    une erreur) ou en cas de problème réseau.
    """
    if not mbid:
        return None
    url = COVER_ART_URL.format(mbid=mbid)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except Exception:
        return None


# ── Cache mémoire des pochettes de CD ──────────────────────────────────
# Les pistes CD n'ont pas de fichier réel (chemin cdda:///D:/track/N), donc
# la pochette récupérée en ligne ne peut pas être écrite dans des tags ID3.
# On la garde simplement en mémoire, par lettre de lecteur, le temps que le
# disque reste inséré/lu.
_cover_cache: dict = {}


def _normalize_drive(drive: str) -> str:
    return drive.rstrip(":")[:1].upper() + ":"


def cache_cover_for_drive(drive: str, cover_bytes: Optional[bytes]):
    if cover_bytes:
        _cover_cache[_normalize_drive(drive)] = cover_bytes


def get_cached_cover_for_drive(drive: str) -> Optional[bytes]:
    return _cover_cache.get(_normalize_drive(drive))


def clear_cover_cache_for_drive(drive: str):
    _cover_cache.pop(_normalize_drive(drive), None)
