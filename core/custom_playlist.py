"""Gestion des playlists personnalisées avec tags d'humeurs"""

import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from enum import Enum
from datetime import datetime
import os

try:
    from .playlist import Track
except (ImportError, ModuleNotFoundError):
    from playlist import Track


class MoodEnum(Enum):
    """6 humeurs disponibles"""
    TRISTE = "Triste"
    MOTIVATION = "Motivation"
    FOCUS = "Focus"
    CHILL = "Chill"
    SOIREE = "Soirée"
    FLOW = "Flow"

    @classmethod
    def get_all_moods(cls):
        """Retourne la liste de toutes les humeurs"""
        return [mood.value for mood in cls]

    @classmethod
    def from_string(cls, value: str):
        """Convertit une string en MoodEnum"""
        for mood in cls:
            if mood.value == value:
                return mood
        raise ValueError(f"Mood '{value}' not found")


@dataclass
class CustomTrack(Track):
    """Extension de Track avec métadonnées audio pour transitions harmonieuses"""
    bpm: Optional[float] = None  # 0 ou None si absent
    key: Optional[str] = None    # Tonalité, ex: "C", "D#", etc. (None si absent)
    energy: Optional[float] = None  # 0.0-1.0 (None si absent)
    genre: Optional[str] = None  # Genre musical (None si absent)

    def to_dict(self) -> dict:
        """Convertit en dictionnaire JSON"""
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CustomTrack":
        """Crée depuis un dictionnaire JSON"""
        return cls(**d)


@dataclass
class CustomPlaylist:
    """Playlist personnalisée avec métadonnées et humeurs"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    moods: List[str] = field(default_factory=list)  # Liste de MoodEnum.value
    cover_path: str = ""  # Chemin relatif ou nom fichier dans playlist_covers/
    tracks: List[CustomTrack] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convertit en dictionnaire JSON"""
        return {
            "id": self.id,
            "name": self.name,
            "moods": self.moods,
            "cover_path": self.cover_path,
            "tracks": [track.to_dict() for track in self.tracks],
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CustomPlaylist":
        """Crée depuis un dictionnaire JSON"""
        tracks = [CustomTrack.from_dict(t) for t in d.get("tracks", [])]
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=d.get("name", ""),
            moods=d.get("moods", []),
            cover_path=d.get("cover_path", ""),
            tracks=tracks,
            created_at=d.get("created_at", datetime.now().isoformat()),
            modified_at=d.get("modified_at", datetime.now().isoformat()),
        )

    def add_track(self, track: CustomTrack):
        """Ajoute une piste à la playlist"""
        self.tracks.append(track)
        self.modified_at = datetime.now().isoformat()

    def add_tracks(self, tracks: List[CustomTrack]):
        """Ajoute plusieurs pistes"""
        self.tracks.extend(tracks)
        self.modified_at = datetime.now().isoformat()

    def remove_track(self, index: int):
        """Retire une piste par index"""
        if 0 <= index < len(self.tracks):
            self.tracks.pop(index)
            self.modified_at = datetime.now().isoformat()

    def set_moods(self, moods: List[str]):
        """Définit les humeurs (valide si ce sont des MoodEnum.value)"""
        # Valider que toutes les humeurs existent
        valid_moods = MoodEnum.get_all_moods()
        for mood in moods:
            if mood not in valid_moods:
                raise ValueError(f"Invalid mood: {mood}")
        self.moods = moods
        self.modified_at = datetime.now().isoformat()

    def clear(self):
        """Vide la playlist"""
        self.tracks.clear()
        self.modified_at = datetime.now().isoformat()


@dataclass
class PlaylistLibrary:
    """Collection de playlists personnalisées"""
    version: int = 1
    playlists: List[CustomPlaylist] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convertit en dictionnaire JSON"""
        return {
            "version": self.version,
            "playlists": [p.to_dict() for p in self.playlists],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PlaylistLibrary":
        """Crée depuis un dictionnaire JSON"""
        playlists = [CustomPlaylist.from_dict(p) for p in d.get("playlists", [])]
        return cls(
            version=d.get("version", 1),
            playlists=playlists,
        )

    def add_playlist(self, playlist: CustomPlaylist):
        """Ajoute une playlist"""
        self.playlists.append(playlist)

    def get_playlist(self, playlist_id: str) -> Optional[CustomPlaylist]:
        """Récupère une playlist par ID"""
        for p in self.playlists:
            if p.id == playlist_id:
                return p
        return None

    def remove_playlist(self, playlist_id: str) -> bool:
        """Supprime une playlist par ID"""
        for i, p in enumerate(self.playlists):
            if p.id == playlist_id:
                self.playlists.pop(i)
                return True
        return False

    def get_playlists_by_mood(self, mood: str) -> List[CustomPlaylist]:
        """Retourne les playlists ayant au moins cette humeur"""
        return [p for p in self.playlists if mood in p.moods]

    def get_all_playlists(self) -> List[CustomPlaylist]:
        """Retourne toutes les playlists"""
        return self.playlists
