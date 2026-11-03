"""Gestion des listes de lecture (.playlist)"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Tuple
from enum import Enum, auto
import random

try:
    from .smart_shuffle_config import SmartShuffleConfig, ShuffleMode
    from .smart_shuffle import (
        select_first_track,
        compatibility_score,
        build_smart_shuffle,
        select_next_track_with_randomness
    )
    SMART_SHUFFLE_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    SMART_SHUFFLE_AVAILABLE = False
    SmartShuffleConfig = None
    ShuffleMode = None


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
        self.loop_mode: Optional[PlayMode] = None
        self._shuffle_order: List[int] = []
        self._shuffle_pos: int = 0
        
        # Shuffle intelligent
        self._smart_shuffle_config: SmartShuffleConfig = None
        self._smart_shuffle_order: List[int] = []
        self._smart_shuffle_pos: int = -1
        self._compatibility_cache: Dict[Tuple[int, int], float] = {}
        
        # Initialiser la config par défaut si disponible
        if SMART_SHUFFLE_AVAILABLE:
            self._smart_shuffle_config = SmartShuffleConfig.default()
        else:
            self._smart_shuffle_config = None


    # --- Propriétés pour le shuffle intelligent ---
    @property
    def smart_shuffle_config(self) -> Optional[SmartShuffleConfig]:
        """Retourne la configuration du shuffle intelligent."""
        return self._smart_shuffle_config

    @smart_shuffle_config.setter
    def smart_shuffle_config(self, config: SmartShuffleConfig):
        """Definit la configuration du shuffle intelligent."""
        if SMART_SHUFFLE_AVAILABLE and isinstance(config, SmartShuffleConfig):
            self._smart_shuffle_config = config
            # Si on est en mode RANDOM et intelligent, reconstruire l'ordre
            if self.play_mode == PlayMode.RANDOM and self._is_smart_mode():
                self._rebuild_smart_shuffle()

    def _is_smart_mode(self) -> bool:
        """Verifie si le mode intelligent est active."""
        if not SMART_SHUFFLE_AVAILABLE or self._smart_shuffle_config is None:
            return False
        return self._smart_shuffle_config.mode == ShuffleMode.INTELLIGENT

    def _get_compatibility(self, idx_a: int, idx_b: int) -> float:
        """
        Recupere ou calcule le score de compatibilite entre deux pistes.
        
        Args:
            idx_a: Index de la premiere piste
            idx_b: Index de la deuxieme piste
        
        Returns:
            Score de compatibilite (0-100)
        """
        if not self._is_smart_mode() or not SMART_SHUFFLE_AVAILABLE:
            return 50.0
        
        key = (idx_a, idx_b)
        if self._smart_shuffle_config.enable_cache and key in self._compatibility_cache:
            return self._compatibility_cache[key]
        
        track_a = self.tracks[idx_a]
        track_b = self.tracks[idx_b]
        score = compatibility_score(track_a, track_b, self._smart_shuffle_config)
        
        if self._smart_shuffle_config.enable_cache:
            self._compatibility_cache[key] = score
        
        return score

    def _select_next_track_with_randomness(self, candidates: List[Tuple[int, float]]) -> int:
        """
        Selectionne la prochaine piste avec le facteur d'aleatoire.
        
        Args:
            candidates: Liste de tuples (index, score)
        
        Returns:
            Index de la piste choisie
        """
        if not candidates:
            return -1
        
        if self._smart_shuffle_config is None:
            return random.choice(candidates)[0]
        
        if self._smart_shuffle_config.randomness_factor == 0.0:
            return candidates[0][0]
        
        if self._smart_shuffle_config.randomness_factor == 1.0:
            return random.choice(candidates)[0]
        
        scores = [score for _, score in candidates]
        max_score = max(scores) if scores else 100.0
        
        weights = []
        for idx, score in candidates:
            norm_score = score / max_score if max_score > 0 else 0.0
            weight = (1.0 - self._smart_shuffle_config.randomness_factor) * norm_score + \
                     self._smart_shuffle_config.randomness_factor * 0.5
            weight = max(0.01, weight)
            weights.append(weight)
        
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        
        chosen_idx, _ = random.choices(candidates, weights=weights, k=1)[0]
        return chosen_idx

    # --- Fin des methodes shuffle intelligent ---

    # ── Ajout / Suppression ──────────────────────────────────────────
    def add_track(self, track: Track) -> int:
        self.tracks.append(track)
        index = len(self.tracks) - 1
        self._add_to_shuffle([index])
        return index

    def add_track_batch(self, tracks: List[Track]) -> int:
        tracks = list(tracks)
        if not tracks:
            return 0

        first_index = len(self.tracks)
        self.tracks.extend(tracks)
        self._add_to_shuffle(list(range(first_index, len(self.tracks))))
        return len(tracks)

    def add_tracks(self, paths: List[str]) -> int:
        new_tracks = []
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in self.ALL_FORMATS:
                new_tracks.append(Track(path=path))
        return self.add_track_batch(new_tracks)

    def remove_track(self, index: int):
        if 0 <= index < len(self.tracks):
            self.tracks.pop(index)
            if self.current_index > index:
                self.current_index -= 1
            elif self.current_index >= len(self.tracks):
                self.current_index = len(self.tracks) - 1
            self._remove_from_shuffle(index)

    def clear(self):
        self.tracks.clear()
        self.current_index = -1
        self._shuffle_order.clear()
        self._shuffle_pos = -1

    def move_track(self, from_idx: int, to_idx: int):
        if 0 <= from_idx < len(self.tracks) and 0 <= to_idx < len(self.tracks):
            t = self.tracks.pop(from_idx)
            self.tracks.insert(to_idx, t)
            self._shuffle_order = [
                to_idx if index == from_idx else
                index - 1 if from_idx < index <= to_idx else
                index + 1 if to_idx <= index < from_idx else index
                for index in self._shuffle_order
            ]
            if self.current_index == from_idx:
                self.current_index = to_idx
            elif from_idx < self.current_index <= to_idx:
                self.current_index -= 1
            elif to_idx <= self.current_index < from_idx:
                self.current_index += 1

    # ── Navigation ───────────────────────────────────────────────────
    @property
    def current_track(self) -> Optional[Track]:
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def set_current(self, index: int) -> Optional[Track]:
        if 0 <= index < len(self.tracks):
            self.current_index = index
            if self.play_mode == PlayMode.RANDOM:
                if not self._shuffle_order:
                    self._rebuild_shuffle()
                self._shuffle_pos = self._shuffle_order.index(index)
            return self.tracks[index]
        return None

    def next_track(self) -> Optional[Track]:
        if not self.tracks:
            return None
        loop_mode = self.loop_mode or (
            self.play_mode
            if self.play_mode in (PlayMode.LOOP_ONE, PlayMode.LOOP_ALL)
            else None
        )
        if loop_mode == PlayMode.LOOP_ONE:
            return self.current_track
        if self.play_mode == PlayMode.RANDOM:
            return self._next_shuffle(loop=loop_mode == PlayMode.LOOP_ALL)
        # SEQUENTIAL or LOOP_ALL
        nxt = self.current_index + 1
        if nxt >= len(self.tracks):
            if loop_mode == PlayMode.LOOP_ALL:
                nxt = 0
            else:
                return None
        self.current_index = nxt
        return self.tracks[self.current_index]

    def prev_track(self) -> Optional[Track]:
        if not self.tracks:
            return None
        loop_mode = self.loop_mode or (
            self.play_mode
            if self.play_mode in (PlayMode.LOOP_ONE, PlayMode.LOOP_ALL)
            else None
        )
        if loop_mode == PlayMode.LOOP_ONE:
            return self.current_track
        if self.play_mode == PlayMode.RANDOM:
            return self._prev_shuffle(loop=loop_mode == PlayMode.LOOP_ALL)
        prv = self.current_index - 1
        if prv < 0:
            if loop_mode == PlayMode.LOOP_ALL:
                prv = len(self.tracks) - 1
            else:
                prv = 0
        self.current_index = prv
        return self.tracks[self.current_index]

    # ── Shuffle helpers ───────────────────────────────────────────────
    def _rebuild_shuffle(self):
        self._shuffle_order = list(range(len(self.tracks)))
        random.shuffle(self._shuffle_order)
        self._shuffle_pos = -1

    def _rebuild_smart_shuffle(self):
        """Reconstruit l'ordre intelligent."""
        if not SMART_SHUFFLE_AVAILABLE or not self._is_smart_mode():
            self._rebuild_shuffle()
            return
        
        # Verifier qu'on a assez de pistes pour le mode intelligent
        if len(self.tracks) > self._smart_shuffle_config.max_tracks_for_smart_mode:
            print("[SmartShuffle] Trop de pistes, passage en mode simple")
            self._rebuild_shuffle()
            return
        
        # Selectionner le premier morceau
        first_idx = select_first_track(
            self.tracks,
            self._smart_shuffle_config,
            self.current_index
        )
        
        self._smart_shuffle_order = [first_idx]
        remaining = [i for i in range(len(self.tracks)) if i != first_idx]
        
        # Construire le reste de l'ordre
        while remaining:
            last_idx = self._smart_shuffle_order[-1]
            last_track = self.tracks[last_idx]
            
            candidates = []
            for idx in remaining:
                candidate_track = self.tracks[idx]
                score = self._get_compatibility(last_idx, idx)
                candidates.append((idx, score))
            
            candidates.sort(key=lambda x: x[1], reverse=True)
            chosen_idx = self._select_next_track_with_randomness(candidates)
            self._smart_shuffle_order.append(chosen_idx)
            remaining.remove(chosen_idx)
        
        self._smart_shuffle_pos = -1


    def _add_to_shuffle(self, new_indices: List[int]):
        """Ajoute des pistes sans refaire l'ordre déjà parcouru."""
        if not SMART_SHUFFLE_AVAILABLE or not self._is_smart_mode():
            # Mode simple
            if not self._shuffle_order or self._shuffle_pos < 0:
                self._rebuild_shuffle()
                return

            random.shuffle(new_indices)
            insert_start = min(self._shuffle_pos + 2, len(self._shuffle_order))
            for index in new_indices:
                insert_at = random.randint(insert_start, len(self._shuffle_order))
                self._shuffle_order.insert(insert_at, index)
                insert_start = min(insert_at + 1, len(self._shuffle_order))
        else:
            # Mode intelligent : reconstruction complète
            self._rebuild_smart_shuffle()

    def _remove_from_shuffle(self, removed_index: int):
        if not SMART_SHUFFLE_AVAILABLE or not self._is_smart_mode():
            # Mode simple
            if not self._shuffle_order:
                return
            removed_pos = self._shuffle_order.index(removed_index)
            self._shuffle_order.pop(removed_pos)
            self._shuffle_order = [
                index - 1 if index > removed_index else index
                for index in self._shuffle_order
            ]
            if removed_pos < self._shuffle_pos:
                self._shuffle_pos -= 1
            elif removed_pos == self._shuffle_pos:
                self._shuffle_pos -= 1
            if not self._shuffle_order:
                self._shuffle_pos = -1
            else:
                self._shuffle_pos = min(self._shuffle_pos, len(self._shuffle_order) - 1)
        else:
            # Mode intelligent : reconstruction complète
            self._rebuild_smart_shuffle()

    def _next_shuffle(self, loop: bool = True) -> Optional[Track]:
        if not SMART_SHUFFLE_AVAILABLE or not self._is_smart_mode():
            # Mode simple
            if not self._shuffle_order:
                self._rebuild_shuffle()
            next_pos = self._shuffle_pos + 1
            if next_pos >= len(self._shuffle_order):
                if not loop and self._shuffle_pos >= 0:
                    return None
                next_pos = 0
            self._shuffle_pos = next_pos
            self.current_index = self._shuffle_order[self._shuffle_pos]
            return self.tracks[self.current_index]
        else:
            # Mode intelligent
            if not self._smart_shuffle_order:
                self._rebuild_smart_shuffle()
            next_pos = self._smart_shuffle_pos + 1
            if next_pos >= len(self._smart_shuffle_order):
                if not loop and self._smart_shuffle_pos >= 0:
                    return None
                next_pos = 0
            self._smart_shuffle_pos = next_pos
            self.current_index = self._smart_shuffle_order[self._smart_shuffle_pos]
            return self.tracks[self.current_index]

    def _prev_shuffle(self, loop: bool = True) -> Optional[Track]:
        if not SMART_SHUFFLE_AVAILABLE or not self._is_smart_mode():
            # Mode simple
            if not self._shuffle_order:
                self._rebuild_shuffle()
            previous_pos = self._shuffle_pos - 1
            if previous_pos < 0:
                if not loop:
                    previous_pos = 0
                else:
                    previous_pos = len(self._shuffle_order) - 1
            self._shuffle_pos = previous_pos
            self.current_index = self._shuffle_order[self._shuffle_pos]
            return self.tracks[self.current_index]
        else:
            # Mode intelligent
            if not self._smart_shuffle_order:
                self._rebuild_smart_shuffle()
            previous_pos = self._smart_shuffle_pos - 1
            if previous_pos < 0:
                if not loop:
                    previous_pos = 0
                else:
                    previous_pos = len(self._smart_shuffle_order) - 1
            self._smart_shuffle_pos = previous_pos
            self.current_index = self._smart_shuffle_order[self._smart_shuffle_pos]
            return self.tracks[self.current_index]

    # ── Persistance ──────────────────────────────────────────────────
    def save(self, filepath: str):
        data = {
            "version": 1,
            "play_mode": self.play_mode.name,
            "loop_mode": self.loop_mode.name if self.loop_mode else "OFF",
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
        loop_mode = data.get("loop_mode")
        if loop_mode in (PlayMode.LOOP_ONE.name, PlayMode.LOOP_ALL.name):
            self.loop_mode = PlayMode[loop_mode]
        elif loop_mode == "OFF":
            self.loop_mode = None
        else:
            self.loop_mode = (
                self.play_mode
                if self.play_mode in (PlayMode.LOOP_ONE, PlayMode.LOOP_ALL)
                else None
            )
        self.current_index = data.get("current_index", 0)
        self._rebuild_shuffle()

    # ── Propriétés utilitaires ────────────────────────────────────────
    def __len__(self):
        return len(self.tracks)

    @property
    def total_duration(self) -> float:
        return sum(t.duration for t in self.tracks)
