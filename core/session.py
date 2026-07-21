"""
Persistance de session SolarSound
Sauvegarde et restaure l'état de l'application entre les sessions.
Le fichier session.json est placé à côté de l'exécutable.
"""

import json
import os
import sys
from dataclasses import dataclass, asdict
from typing import Optional


def _session_path() -> str:
    """
    Retourne le chemin du fichier session.json.
    - En mode .exe PyInstaller : à côté du .exe
    - En mode script Python   : à côté de main.py
    """
    if getattr(sys, "frozen", False):
        # Exécutable PyInstaller
        base = os.path.dirname(sys.executable)
    else:
        # Script Python : remonter au dossier racine (là où est main.py)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "solarsound_session.json")


@dataclass
class WindowState:
    x: int = 100
    y: int = 100
    width: int = 1080
    height: int = 720
    screen_name: str = ""        # Nom/index de l'écran pour restaurer le bon moniteur
    maximized: bool = False


@dataclass
class SessionState:
    # Fenêtre
    window: WindowState = None

    # Playlist
    playlist_path: str = ""      # Dernière playlist chargée (si sauvegardée)
    playlist_tracks: list = None # Chemins des pistes en mémoire
    current_index: int = 0
    play_mode: str = "SEQUENTIAL"

    # Audio
    volume: int = 100
    spatial_config: dict = None

    vinyl_config: dict = None

    # Paramètres UI
    shortcuts: dict = None
    colors: dict = None
    font_cfg: dict = None

    def __post_init__(self):
        if self.window is None:
            self.window = WindowState()
        if self.playlist_tracks is None:
            self.playlist_tracks = []
        if self.spatial_config is None:
            self.spatial_config = {}
        if self.vinyl_config is None:
            self.vinyl_config = {}
        if self.shortcuts is None:
            self.shortcuts = {}
        if self.colors is None:
            self.colors = {}
        if self.font_cfg is None:
            self.font_cfg = {}


class SessionManager:
    """Gère la sauvegarde et le chargement de la session"""

    def __init__(self):
        self._path = _session_path()

    @property
    def path(self) -> str:
        return self._path

    def save(self, state: SessionState):
        try:
            data = {
                "version": 2,
                "window": asdict(state.window),
                "playlist_tracks": state.playlist_tracks,
                "current_index": state.current_index,
                "play_mode": state.play_mode,
                "volume": state.volume,
                "spatial_config": state.spatial_config,
                "vinyl_config": getattr(state, "vinyl_config", {}),
                "shortcuts": getattr(state, "shortcuts", {}),
                "colors": getattr(state, "colors", {}),
                "font_cfg": getattr(state, "font_cfg", {}),
            }
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Session] Impossible de sauvegarder : {e}")

    def load(self) -> SessionState:
        state = SessionState()
        if not os.path.exists(self._path):
            return state
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)

            w = data.get("window", {})
            state.window = WindowState(
                x=w.get("x", 100),
                y=w.get("y", 100),
                width=w.get("width", 1080),
                height=w.get("height", 720),
                screen_name=w.get("screen_name", ""),
                maximized=w.get("maximized", False),
            )
            state.playlist_tracks = data.get("playlist_tracks", [])
            state.current_index   = data.get("current_index", 0)
            state.play_mode       = data.get("play_mode", "SEQUENTIAL")
            state.volume          = data.get("volume", 100)
            state.spatial_config  = data.get("spatial_config", {})
            state.vinyl_config    = data.get("vinyl_config", {})
            state.shortcuts       = data.get("shortcuts", {})
            state.colors          = data.get("colors", {})
            state.font_cfg        = data.get("font_cfg", {})
        except Exception as e:
            print(f"[Session] Impossible de charger : {e}")
        return state
