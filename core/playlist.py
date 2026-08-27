"""Gestion des listes de lecture (.playlist)"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from enum import Enum, auto
import random


class PlayMode(Enum):
    SEQUENTIAL = auto()   # Tout droit
    LOOP_ONE = auto()     # Boucle sur le fichier
    LOOP_ALL = auto()     # Boucle toute la liste
    RANDOM = auto()       # Aléatoire


@dataclass
class Track:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0  # en secondes

    def __post_init__(self):
        if not self.title:
            self.title = os.path.splitext(os.path.basename(self.path))[0]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        return cls(**d)


class Playlist:
    SUPPORTED_FORMATS = (
        ".mp3", ".wav", ".flac", ".ogg", ".opus", ".aiff", ".aif",
        ".au", ".rf64", ".w64",
    )
    SUPPORTED_VIDEO_FORMATS = (".mp4", ".mkv", ".avi", ".mov", ".wmv",
                               ".dts", ".m4v", ".flv", ".webm",
                               ".ts", ".m2ts", ".mpg", ".mpeg")
    ALL_FORMATS = SUPPORTED_FORMATS + SUPPORTED_VIDEO_FORMATS

    def __init__(self):
        self.tracks: List[Track] = []
        self.current_index: int = -1
        self.play_mode: PlayMode = PlayMode.SEQUENTIAL
        self._shuffle_order: List[int] = []
        self._shuffle_pos: int = 0

    # ── Ajout / Suppression ──────────────────────────────────────────
    def add_track(self, track: Track) -> int:
        self.tracks.append(track)
        self._rebuild_shuffle()
        return len(self.tracks) - 1

    def add_tracks(self, paths: List[str]) -> int:
        added = 0
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in self.ALL_FORMATS:
                self.tracks.append(Track(path=p))
                added += 1
        self._rebuild_shuffle()
        return added

    def remove_track(self, index: int):
        if 0 <= index < len(self.tracks):
            self.tracks.pop(index)
            if self.current_index >= len(self.tracks):
                self.current_index = len(self.tracks) - 1
            self._rebuild_shuffle()

    def clear(self):
        self.tracks.clear()
        self.current_index = -1
        self._shuffle_order.clear()

    def move_track(self, from_idx: int, to_idx: int):
        if 0 <= from_idx < len(self.tracks) and 0 <= to_idx < len(self.tracks):
            t = self.tracks.pop(from_idx)
            self.tracks.insert(to_idx, t)
            self._rebuild_shuffle()

    # ── Navigation ───────────────────────────────────────────────────
    @property
    def current_track(self) -> Optional[Track]:
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def set_current(self, index: int) -> Optional[Track]:
        if 0 <= index < len(self.tracks):
            self.current_index = index
            return self.tracks[index]
        return None

    def next_track(self) -> Optional[Track]:
        if not self.tracks:
            return None
        if self.play_mode == PlayMode.LOOP_ONE:
            return self.current_track
        if self.play_mode == PlayMode.RANDOM:
            return self._next_shuffle()
        # SEQUENTIAL or LOOP_ALL
        nxt = self.current_index + 1
        if nxt >= len(self.tracks):
            if self.play_mode == PlayMode.LOOP_ALL:
                nxt = 0
            else:
                return None
        self.current_index = nxt
        return self.tracks[self.current_index]

    def prev_track(self) -> Optional[Track]:
        if not self.tracks:
            return None
        if self.play_mode == PlayMode.LOOP_ONE:
            return self.current_track
        if self.play_mode == PlayMode.RANDOM:
            return self._prev_shuffle()
        prv = self.current_index - 1
        if prv < 0:
            if self.play_mode == PlayMode.LOOP_ALL:
                prv = len(self.tracks) - 1
            else:
                prv = 0
        self.current_index = prv
        return self.tracks[self.current_index]

    # ── Shuffle helpers ───────────────────────────────────────────────
    def _rebuild_shuffle(self):
        self._shuffle_order = list(range(len(self.tracks)))
        random.shuffle(self._shuffle_order)
        self._shuffle_pos = 0

    def _next_shuffle(self) -> Optional[Track]:
        if not self._shuffle_order:
            self._rebuild_shuffle()
        self._shuffle_pos = (self._shuffle_pos + 1) % len(self._shuffle_order)
        self.current_index = self._shuffle_order[self._shuffle_pos]
        return self.tracks[self.current_index]

    def _prev_shuffle(self) -> Optional[Track]:
        if not self._shuffle_order:
            self._rebuild_shuffle()
        self._shuffle_pos = (self._shuffle_pos - 1) % len(self._shuffle_order)
        self.current_index = self._shuffle_order[self._shuffle_pos]
        return self.tracks[self.current_index]

    # ── Persistance ──────────────────────────────────────────────────
    def save(self, filepath: str):
        data = {
            "version": 1,
            "play_mode": self.play_mode.name,
            "current_index": self.current_index,
            "tracks": [t.to_dict() for t in self.tracks],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.clear()
        for td in data.get("tracks", []):
            self.tracks.append(Track.from_dict(td))
        try:
            self.play_mode = PlayMode[data.get("play_mode", "SEQUENTIAL")]
        except KeyError:
            self.play_mode = PlayMode.SEQUENTIAL
        self.current_index = data.get("current_index", 0)
        self._rebuild_shuffle()

    # ── Propriétés utilitaires ────────────────────────────────────────
    def __len__(self):
        return len(self.tracks)

    @property
    def total_duration(self) -> float:
        return sum(t.duration for t in self.tracks)
