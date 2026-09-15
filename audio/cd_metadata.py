"""
Récupération automatique des métadonnées d'un CD audio (titre, artiste,
album, pochette) à partir du sommaire du disque (TOC).

Stratégie de recherche, dans l'ordre (comme le font EAC / CUETools) :

1. **Disc ID MusicBrainz exact** (SHA-1 du TOC) → /ws/2/discid/{id}
   C'est une correspondance *exacte* : soit le disque est connu, soit non.
2. **CUETools DB** (base alimentée par les rippeurs, très fournie sur les
   disques que MusicBrainz ignore), interrogée avec le même TOC.
3. **Recherche floue MusicBrainz** (?toc=…) en dernier recours, avec un
   score pour départager les candidats.

Aucune dépendance supplémentaire : uniquement la bibliothèque standard.
"""

import base64
import hashlib
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Optional, List, Tuple


MB_DISCID_URL = "https://musicbrainz.org/ws/2/discid/{discid}"
MB_FUZZY_URL = "https://musicbrainz.org/ws/2/discid/-"
COVER_ART_URL = "https://coverartarchive.org/release/{mbid}/front-500"
CTDB_URL = "http://db.cuetools.net/lookup2.php"

# MusicBrainz impose un en-tête User-Agent identifiant l'application
# (obligatoire, sous peine de blocage des requêtes). Personnalisez cette
# valeur si vous distribuez l'application sous un autre nom/contact.
USER_AGENT = "SolarSound-MusicPlayer/1.0 ( https://github.com/BalzaTer/SolarSound )"

# Écart lead-out/lead-in + pré-gap entre la session audio et une session
# de données sur un CD "enhanced" (cf. MusicBrainz Disc ID Calculation).
DATA_SESSION_GAP = 11400

DATA_TRACK_FLAG = 0x04  # bit "Control" indiquant une piste de données


# ── Analyse du TOC ─────────────────────────────────────────────────────

def audio_toc(toc: dict) -> Optional[Tuple[int, int, int, List[int]]]:
    """
    Réduit un TOC brut à sa partie **audio uniquement**, telle qu'attendue
    par MusicBrainz et CDDB.

    Les CD "enhanced" (très courants dans les années 90-2000) ont une piste
    de données en dernière position. Elle ne doit pas entrer dans le calcul
    de l'identifiant, et le lead-out à utiliser est le début de cette piste
    de données moins 11400 frames.

    Returns:
        (first_track, last_track, leadout, offsets_audio) ou None si le TOC
        est inexploitable / ne contient aucune piste audio.
    """
    try:
        first = int(toc["first_track"])
        offsets = list(toc["track_offsets"])
        leadout = int(toc["leadout_offset"])
    except (KeyError, TypeError, ValueError):
        return None

    if not offsets:
        return None

    # Sans information de contrôle, on suppose que tout est audio (ancien
    # comportement) plutôt que d'échouer.
    controls = list(toc.get("track_controls") or [])
    if len(controls) != len(offsets):
        controls = [0] * len(offsets)

    is_data = [bool(c & DATA_TRACK_FLAG) for c in controls]

    # On ne garde que le bloc audio initial : une piste de données en tête
    # (CD-Extra inversé, rarissime) ou au milieu casse la numérotation
    # attendue par MusicBrainz, on préfère alors ne rien affirmer.
    if is_data[0]:
        return None

    audio_count = len(offsets)
    for i, data in enumerate(is_data):
        if data:
            audio_count = i
            break

    if audio_count == 0:
        return None

    if audio_count < len(offsets):
        # Le lead-out effectif = début de la 1re piste de données - 11400
        leadout = offsets[audio_count] - DATA_SESSION_GAP

    audio_offsets = offsets[:audio_count]
    last = first + audio_count - 1

    if leadout <= audio_offsets[-1]:
        return None  # TOC incohérent

    return first, last, leadout, audio_offsets


def compute_disc_id(toc: dict) -> Optional[str]:
    """
    Calcule le Disc ID MusicBrainz (28 caractères) d'un TOC.

    Algorithme officiel : SHA-1 de la chaîne ASCII composée du numéro de
    première piste (%02X), de dernière piste (%02X), puis de 100 offsets
    sur 8 chiffres hexadécimaux (indice 0 = lead-out, 1..99 = pistes,
    complété par des zéros) ; puis base64 avec « + / = » remplacés par
    « . _ - ».
    """
    parsed = audio_toc(toc)
    if not parsed:
        return None
    first, last, leadout, offsets = parsed

    entries = [0] * 100
    entries[0] = leadout
    for index, offset in enumerate(offsets):
        track_number = first + index
        if 1 <= track_number <= 99:
            entries[track_number] = offset

    payload = "%02X%02X" % (first, last) + "".join("%08X" % e for e in entries)
    digest = hashlib.sha1(payload.encode("ascii")).digest()
    return (base64.b64encode(digest).decode("ascii")
            .replace("+", ".").replace("/", "_").replace("=", "-"))


def compute_freedb_id(toc: dict) -> Optional[str]:
    """Calcule l'identifiant FreeDB/CDDB (8 chiffres hexadécimaux)."""
    parsed = audio_toc(toc)
    if not parsed:
        return None
    first, last, leadout, offsets = parsed

    def digit_sum(n: int) -> int:
        total = 0
        while n > 0:
            total += n % 10
            n //= 10
        return total

    checksum = sum(digit_sum(o // 75) for o in offsets)
    total_seconds = (leadout // 75) - (offsets[0] // 75)
    disc_id = ((checksum % 255) << 24) | (total_seconds << 8) | len(offsets)
    return "%08x" % (disc_id & 0xFFFFFFFF)


def build_toc_string(toc: dict) -> Optional[str]:
    """
    Construit le paramètre TOC textuel attendu par MusicBrainz (recherche
    floue) et CUETools DB : « premier dernier leadout off1 off2 … ».
    """
    parsed = audio_toc(toc)
    if not parsed:
        return None
    first, last, leadout, offsets = parsed
    return " ".join(str(v) for v in ([first, last, leadout] + offsets))


def toc_track_lengths_ms(toc: dict) -> Optional[List[int]]:
    """
    Durée de chaque piste audio, en millisecondes, déduite du TOC.

    C'est la signature la plus discriminante d'un disque : deux albums sans
    rapport peuvent avoir le même nombre de pistes, mais quasiment jamais
    les mêmes durées à la seconde près.
    """
    parsed = audio_toc(toc)
    if not parsed:
        return None
    _, _, leadout, offsets = parsed
    bounds = offsets + [leadout]
    return [int((bounds[i + 1] - bounds[i]) * 1000 / 75) for i in range(len(offsets))]


def _lengths_match(toc_lengths: List[int], release_lengths: List[Optional[int]],
                   tolerance_ms: int = 4000) -> bool:
    """
    Vérifie que les durées d'une release correspondent à celles du disque.

    Tolérance volontairement large (4 s) : les durées MusicBrainz sont
    parfois saisies à la main ou proviennent d'une autre édition. Une piste
    sans durée connue n'invalide pas la correspondance, mais il en faut une
    majorité de renseignées pour conclure.
    """
    if not toc_lengths or len(toc_lengths) != len(release_lengths):
        return False

    known = [(a, b) for a, b in zip(toc_lengths, release_lengths) if b]
    if len(known) < max(1, len(toc_lengths) // 2):
        return False  # trop peu de durées connues pour trancher

    return all(abs(a - b) <= tolerance_ms for a, b in known)


# ── Requêtes HTTP ──────────────────────────────────────────────────────

def _http_get(url: str, timeout: float) -> Optional[bytes]:
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml;q=0.9, */*;q=0.5",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except Exception as e:
        print(f"[CdMetadata] Requête échouée ({url.split('?')[0]}) : {e}")
        return None


# ── Extraction d'une release MusicBrainz ───────────────────────────────

def _parse_release(release: dict, disc_id: Optional[str],
                   expected_track_count: int) -> dict:
    """Convertit une release de l'API MusicBrainz au format interne."""
    album = release.get("title", "") or ""

    artist = ""
    credits = release.get("artist-credit") or []
    if credits:
        artist = credits[0].get("name") or (credits[0].get("artist") or {}).get("name", "")

    year = (release.get("date") or "")[:4]

    # Une release peut contenir plusieurs disques (coffret) : il faut
    # choisir le bon medium, pas systématiquement le premier.
    media = release.get("media") or []
    chosen = None
    if disc_id:
        for medium in media:
            if any(d.get("id") == disc_id for d in (medium.get("discs") or [])):
                chosen = medium
                break
    if chosen is None:
        for medium in media:
            if medium.get("track-count") == expected_track_count:
                chosen = medium
                break
    if chosen is None and media:
        chosen = media[0]

    tracks = []
    track_lengths: List[Optional[int]] = []
    if chosen:
        for t in chosen.get("tracks", []):
            recording = t.get("recording") or {}
            title = t.get("title") or recording.get("title") or ""
            tracks.append(title)
            length = t.get("length") or recording.get("length")
            track_lengths.append(int(length) if length else None)

    return {
        "mbid": release.get("id"),
        "album": album,
        "artist": artist,
        "year": year,
        "tracks": tracks,
        "track_lengths": track_lengths,
        "source": "musicbrainz",
        "exact": bool(disc_id),
    }


def _score_release(parsed: dict, expected_track_count: int) -> int:
    """
    Note une release candidate issue de la recherche *floue*, pour éviter
    de retomber systématiquement sur `releases[0]`, qui est la cause
    principale des « mauvais disques » identifiés.
    """
    score = 0
    if len(parsed.get("tracks") or []) == expected_track_count:
        score += 100
    if all(parsed.get("tracks") or ["" ]):
        score += 20  # aucun titre vide
    if parsed.get("artist"):
        score += 10
    if parsed.get("year"):
        score += 5
    if parsed.get("album"):
        score += 5
    return score


def fetch_release_by_discid(toc: dict, timeout: float = 8.0) -> Optional[dict]:
    """Correspondance **exacte** par Disc ID MusicBrainz."""
    disc_id = compute_disc_id(toc)
    if not disc_id:
        return None

    query = urllib.parse.urlencode({
        "fmt": "json",
        "inc": "recordings+artist-credits+discids",
        "cdstubs": "no",
    })
    raw = _http_get(f"{MB_DISCID_URL.format(discid=disc_id)}?{query}", timeout)
    if not raw:
        return None

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None

    releases = data.get("releases") or []
    if not releases:
        return None

    parsed = audio_toc(toc)
    expected = len(parsed[3]) if parsed else 0

    candidates = [_parse_release(r, disc_id, expected) for r in releases]
    # Même en correspondance exacte, plusieurs éditions peuvent partager le
    # disc ID : on prend celle dont la liste de pistes est la plus complète.
    candidates.sort(key=lambda c: _score_release(c, expected), reverse=True)
    return candidates[0]


def fetch_release_fuzzy(toc: dict, timeout: float = 8.0) -> Optional[dict]:
    """Recherche floue MusicBrainz par TOC (dernier recours)."""
    toc_str = build_toc_string(toc)
    if not toc_str:
        return None

    query = urllib.parse.urlencode({
        "toc": toc_str,
        "fmt": "json",
        "inc": "recordings+artist-credits",
        "cdstubs": "no",
    })
    raw = _http_get(f"{MB_FUZZY_URL}?{query}", timeout)
    if not raw:
        return None

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None

    releases = data.get("releases") or []
    if not releases:
        return None

    parsed = audio_toc(toc)
    expected = len(parsed[3]) if parsed else 0
    toc_lengths = toc_track_lengths_ms(toc) or []

    candidates = [_parse_release(r, None, expected) for r in releases]

    # Filtre décisif : en recherche floue, MusicBrainz renvoie volontiers
    # des disques sans rapport qui ont simplement le même nombre de pistes.
    # Seules les durées permettent de les écarter.
    verified = [
        c for c in candidates
        if _lengths_match(toc_lengths, c.get("track_lengths") or [])
    ]
    if not verified:
        print("[CdMetadata] Recherche floue : aucun candidat dont les durées "
              "correspondent au disque — résultat ignoré.")
        return None

    verified.sort(key=lambda c: _score_release(c, expected), reverse=True)
    best = verified[0]
    best["exact"] = False
    return best


def fetch_release_from_ctdb(toc: dict, timeout: float = 8.0) -> Optional[dict]:
    """
    Interroge la base CUETools (CTDB), qui couvre beaucoup de disques
    absents de MusicBrainz. Réponse au format XML.
    """
    toc_str = build_toc_string(toc)
    if not toc_str:
        return None

    query = urllib.parse.urlencode({
        "version": "3",
        "ctdb": "1",
        "metadata": "extensive",
        "fuzzy": "0",
        "toc": toc_str.replace(" ", ":"),
    })
    raw = _http_get(f"{CTDB_URL}?{query}", timeout)
    if not raw:
        return None

    try:
        root = ET.fromstring(raw)
    except Exception:
        return None

    entry = root.find(".//metadata")
    if entry is None:
        return None

    album = entry.get("album") or ""
    artist = entry.get("artist") or ""
    year = (entry.get("year") or "")[:4]
    tracks = [t.get("name") or "" for t in entry.findall(".//track")]

    if not album and not tracks:
        return None

    return {
        "mbid": None,  # pas de pochette Cover Art Archive dans ce cas
        "album": album,
        "artist": artist,
        "year": year,
        "tracks": tracks,
        "source": "ctdb",
        "exact": True,
    }


def fetch_release_by_toc(toc: dict, timeout: float = 8.0) -> Optional[dict]:
    """
    Point d'entrée principal : essaie les sources dans l'ordre exact →
    CUETools → flou. Conserve le nom historique pour ne rien casser côté
    interface.

    Returns:
        dict avec les clés mbid, album, artist, year, tracks, source,
        exact — ou None si aucune source ne reconnaît le disque.
    """
    for lookup in (fetch_release_by_discid, fetch_release_from_ctdb, fetch_release_fuzzy):
        result = lookup(toc, timeout=timeout)
        if result:
            print(f"[CdMetadata] Disque identifié via {result.get('source')} "
                  f"(exact={result.get('exact')}) : {result.get('artist')} — {result.get('album')}")
            return result

    print(f"[CdMetadata] Disque non identifié "
          f"(disc id MusicBrainz : {compute_disc_id(toc)}, "
          f"FreeDB : {compute_freedb_id(toc)})")
    return None


def submission_url(toc: dict) -> Optional[str]:
    """
    URL permettant d'ajouter soi-même le disque à MusicBrainz quand il est
    inconnu — utile à proposer à l'utilisateur plutôt que d'échouer
    silencieusement.
    """
    disc_id = compute_disc_id(toc)
    toc_str = build_toc_string(toc)
    if not disc_id or not toc_str:
        return None
    query = urllib.parse.urlencode({"toc": toc_str.replace(" ", "+"), "tracks": len(toc_str.split()) - 3})
    return f"https://musicbrainz.org/cdtoc/attach?id={disc_id}&{query}"


def diagnose(toc: dict) -> str:
    """
    Résumé de diagnostic : identifiants calculés, TOC audio retenu, durées,
    et URL à ouvrir dans un navigateur pour vérifier ce que MusicBrainz
    répond réellement pour ce disque.

    À appeler depuis une console Python quand un disque est mal identifié :
        from audio.cd import CdAudio
        from audio.cd_metadata import diagnose
        print(diagnose(CdAudio.read_toc("D:")))
    """
    lines = []
    parsed = audio_toc(toc)
    lines.append(f"TOC brut          : {toc}")
    if not parsed:
        lines.append("TOC audio         : INEXPLOITABLE (pistes de données en tête ?)")
        return "\n".join(lines)

    first, last, leadout, offsets = parsed
    lines.append(f"Pistes audio      : {first}..{last} ({len(offsets)} pistes)")
    lines.append(f"Lead-out          : {leadout}")
    lines.append(f"Offsets           : {offsets}")

    lengths = toc_track_lengths_ms(toc) or []
    lines.append("Durées            : " + ", ".join(
        f"{ms // 60000}:{(ms // 1000) % 60:02d}" for ms in lengths
    ))

    disc_id = compute_disc_id(toc)
    lines.append(f"Disc ID MusicBrainz : {disc_id}")
    lines.append(f"ID FreeDB/CDDB      : {compute_freedb_id(toc)}")
    lines.append(f"Vérifier ici        : https://musicbrainz.org/ws/2/discid/{disc_id}?fmt=json&inc=recordings+artist-credits")
    lines.append(f"Page web            : https://musicbrainz.org/cdtoc/{disc_id}")
    return "\n".join(lines)


def fetch_cover_art(mbid: str, timeout: float = 8.0) -> Optional[bytes]:
    """
    Récupère la pochette d'une release MusicBrainz via Cover Art Archive.
    Retourne None si aucune pochette n'est disponible (cas normal, pas
    une erreur) ou en cas de problème réseau.
    """
    if not mbid:
        return None
    request = urllib.request.Request(
        COVER_ART_URL.format(mbid=mbid), headers={"User-Agent": USER_AGENT}
    )
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
