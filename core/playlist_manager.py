"""Gestionnaire central des playlists personnalisées"""

import json
import os
import sys
from typing import List, Optional
from datetime import datetime

try:
    from .custom_playlist import (
        CustomPlaylist, CustomTrack, PlaylistLibrary,
        MoodEnum
    )
    from .cover_handler import CoverHandler
except (ImportError, ModuleNotFoundError):
    from custom_playlist import (
        CustomPlaylist, CustomTrack, PlaylistLibrary,
        MoodEnum
    )
    from cover_handler import CoverHandler


class PlaylistManager:
    """Orchestration centralisée des playlists personnalisées"""

    PLAYLISTS_FILENAME = "solarsound_playlists.json"

    def __init__(self, app_data_dir: Optional[str] = None):
        """
        Initialise le gestionnaire de playlists.
        
        Args:
            app_data_dir: Répertoire de base (généré auto si None)
        """
        if app_data_dir is None:
            app_data_dir = self._get_app_data_dir()
        
        self.app_data_dir = app_data_dir
        self.playlists_path = os.path.join(app_data_dir, self.PLAYLISTS_FILENAME)
        self.cover_handler = CoverHandler(app_data_dir)
        self.library = PlaylistLibrary()

    @staticmethod
    def _get_app_data_dir() -> str:
        """Détermine le répertoire de base (exe ou racine script)"""
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # ── Sauvegarde / Chargement ──────────────────────────────────────

    def load_all(self) -> bool:
        """
        Charge toutes les playlists depuis JSON.
        
        Returns:
            True si succès, False sinon
        """
        if not os.path.exists(self.playlists_path):
            self.library = PlaylistLibrary()
            return True

        try:
            with open(self.playlists_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.library = PlaylistLibrary.from_dict(data)
            return True
        except Exception as e:
            print(f"[PlaylistManager] Erreur chargement: {e}")
            self.library = PlaylistLibrary()
            return False

    def save_all(self) -> bool:
        """
        Sauvegarde toutes les playlists en JSON.
        
        Returns:
            True si succès, False sinon
        """
        try:
            with open(self.playlists_path, "w", encoding="utf-8") as f:
                json.dump(self.library.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[PlaylistManager] Erreur sauvegarde: {e}")
            return False

    # ── CRUD Playlists ──────────────────────────────────────────────

    def create_playlist(self, name: str, moods: Optional[List[str]] = None) -> CustomPlaylist:
        """
        Crée une nouvelle playlist.
        
        Args:
            name: Nom de la playlist
            moods: Liste optionnelle d'humeurs
            
        Returns:
            Playlist créée
        """
        playlist = CustomPlaylist(name=name)
        if moods:
            playlist.set_moods(moods)
        self.library.add_playlist(playlist)
        self.save_all()
        return playlist

    def get_playlist(self, playlist_id: str) -> Optional[CustomPlaylist]:
        """Récupère une playlist par ID"""
        return self.library.get_playlist(playlist_id)

    def get_all_playlists(self) -> List[CustomPlaylist]:
        """Retourne toutes les playlists"""
        return self.library.get_all_playlists()

    def update_playlist(self, playlist_id: str, **kwargs) -> bool:
        """
        Met à jour une playlist.
        
        Args:
            playlist_id: ID de la playlist
            **kwargs: Champs à mettre à jour (name, moods, cover_path)
            
        Returns:
            True si succès, False sinon
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False

        if "name" in kwargs:
            playlist.name = kwargs["name"]
        if "moods" in kwargs:
            try:
                playlist.set_moods(kwargs["moods"])
            except ValueError:
                return False
        if "cover_path" in kwargs:
            playlist.cover_path = kwargs["cover_path"]

        playlist.modified_at = datetime.now().isoformat()
        self.save_all()
        return True

    def delete_playlist(self, playlist_id: str) -> bool:
        """
        Supprime une playlist et son cover.
        
        Args:
            playlist_id: ID de la playlist
            
        Returns:
            True si succès, False sinon
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False

        # Supprimer le cover si existant
        if playlist.cover_path:
            self.cover_handler.delete_cover(playlist.cover_path)

        # Supprimer la playlist
        success = self.library.remove_playlist(playlist_id)
        if success:
            self.save_all()
        return success

    # ── Gestion des pistes ──────────────────────────────────────────

    def add_tracks_to_playlist(self, playlist_id: str, file_paths: List[str]) -> int:
        """
        Ajoute des fichiers audio à une playlist.
        
        Args:
            playlist_id: ID de la playlist
            file_paths: Liste de chemins fichiers
            
        Returns:
            Nombre de pistes ajoutées
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return 0

        from core.playlist import Playlist
        from audio.metadata import read_metadata
        from audio.audio_analysis import extract_audio_metadata
        supported = set(Playlist.SUPPORTED_FORMATS + Playlist.SUPPORTED_VIDEO_FORMATS)

        added = 0
        for path in file_paths:
            if not os.path.exists(path):
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext not in supported:
                continue

            # Créer CustomTrack depuis fichier + extraire métadonnées
            # (titre/artiste/durée + bpm/tonalité/énergie/genre pour le Flow)
            info = read_metadata(path)
            audio_meta = extract_audio_metadata(path)
            track = CustomTrack(
                path=path,
                title=info.get("title", ""),
                artist=info.get("artist", ""),
                album=info.get("album", ""),
                duration=audio_meta.get("duration") or info.get("duration", 0.0),
                bpm=audio_meta.get("bpm"),
                key=audio_meta.get("key"),
                energy=audio_meta.get("energy"),
                genre=audio_meta.get("genre"),
            )
            playlist.add_track(track)
            added += 1

        if added > 0:
            self.save_all()
        return added

    def add_folder_to_playlist(self, playlist_id: str, folder_path: str) -> int:
        """
        Ajoute tous les fichiers d'un dossier (récursivement) à une playlist.
        
        Args:
            playlist_id: ID de la playlist
            folder_path: Chemin du dossier
            
        Returns:
            Nombre de pistes ajoutées
        """
        if not os.path.isdir(folder_path):
            return 0

        from core.playlist import Playlist
        supported = set(Playlist.SUPPORTED_FORMATS + Playlist.SUPPORTED_VIDEO_FORMATS)

        added = 0
        for root, dirs, files in os.walk(folder_path):
            for file in sorted(files):
                ext = os.path.splitext(file)[1].lower()
                if ext not in supported:
                    continue
                path = os.path.join(root, file)
                added += self.add_tracks_to_playlist(playlist_id, [path])

        return added

    def remove_track_from_playlist(self, playlist_id: str, track_index: int) -> bool:
        """Retire une piste d'une playlist par index"""
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False
        playlist.remove_track(track_index)
        self.save_all()
        return True

    def reorder_playlist_tracks(self, playlist_id: str, new_order: List[int]) -> bool:
        """
        Réordonne les pistes d'une playlist.

        Args:
            playlist_id: ID de la playlist
            new_order: nouvelle séquence d'index (0-based) référant l'ordre actuel
                       des pistes, ex: [2, 0, 1] déplace la 3e piste en tête.

        Returns:
            True si succès, False si new_order est invalide
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False
        if sorted(new_order) != list(range(len(playlist.tracks))):
            return False
        playlist.tracks = [playlist.tracks[i] for i in new_order]
        playlist.modified_at = datetime.now().isoformat()
        self.save_all()
        return True

    def clear_playlist(self, playlist_id: str) -> bool:
        """Vide une playlist"""
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False
        playlist.clear()
        self.save_all()
        return True

    # ── Gestion des humeurs ─────────────────────────────────────────

    def set_playlist_moods(self, playlist_id: str, moods: List[str]) -> bool:
        """
        Définit les humeurs d'une playlist.
        
        Args:
            playlist_id: ID de la playlist
            moods: Liste de MoodEnum.value
            
        Returns:
            True si succès, False sinon
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False
        try:
            playlist.set_moods(moods)
            self.save_all()
            return True
        except ValueError:
            return False

    def get_playlists_by_mood(self, mood: str) -> List[CustomPlaylist]:
        """Retourne les playlists ayant cette humeur"""
        return self.library.get_playlists_by_mood(mood)

    # ── Génération Mix Flow ─────────────────────────────────────────

    def generate_flow(self, moods: List[str]) -> List[CustomTrack]:
        """
        Génère un mix harmonieux pour une liste d'humeurs.
        
        Inclut TOUTES les pistes même sans métadonnées (BPM/tonalité/énergie).
        Pistes avec métadonnées sont ordonnées pour transitions harmonieuses.
        Pistes sans métadonnées sont distribuées dans le mix.
        
        Args:
            moods: Liste de MoodEnum.value
            
        Returns:
            Liste de CustomTrack ordonnée pour le flow
        """
        # Récupérer toutes les pistes des playlists avec au moins une humeur
        all_tracks = []
        for mood in moods:
            playlists = self.get_playlists_by_mood(mood)
            for playlist in playlists:
                all_tracks.extend(playlist.tracks)

        if not all_tracks:
            return []

        # Séparer pistes avec/sans métadonnées
        tracks_with_metadata = []
        tracks_without_metadata = []

        for track in all_tracks:
            if track.bpm is not None and track.bpm > 0:
                tracks_with_metadata.append(track)
            else:
                tracks_without_metadata.append(track)

        # Ordonnancer pistes avec métadonnées par transitions harmonieuses
        if tracks_with_metadata:
            ordered = self._order_tracks_by_flow(tracks_with_metadata)
        else:
            ordered = []

        # Insérer pistes sans métadonnées dans les espaces (fin de chaîne)
        result = ordered + tracks_without_metadata

        return result

    def _order_tracks_by_flow(self, tracks: List[CustomTrack]) -> List[CustomTrack]:
        """
        Ordonne les pistes avec métadonnées pour transitions harmonieuses.
        
        Critères (par ordre de priorité) :
        1. Écart BPM minimal (< 10 BPM = bon)
        2. Tonalité voisine (intervalles consonants)
        3. Continuité d'énergie
        4. Genre compatible
        
        Utilise un algorithme greedy (rapide, suffisant pour < 1000 pistes).
        """
        if not tracks or len(tracks) <= 1:
            return tracks

        # Démarrer par une piste aléatoire ou la première
        result = [tracks[0]]
        remaining = set(range(1, len(tracks)))

        while remaining:
            current = result[-1]
            best_idx = None
            best_score = -float('inf')

            # Trouver la piste suivante avec meilleur score de transition
            for idx in remaining:
                candidate = tracks[idx]
                score = self._score_transition(current, candidate)
                if score > best_score:
                    best_score = score
                    best_idx = idx

            if best_idx is not None:
                result.append(tracks[best_idx])
                remaining.remove(best_idx)
            else:
                # Fallback : ajouter une piste aléatoire
                idx = remaining.pop()
                result.append(tracks[idx])

        return result

    @staticmethod
    def _score_transition(track1: CustomTrack, track2: CustomTrack) -> float:
        """
        Calcule un score de transition entre deux pistes.
        Plus élevé = meilleure transition.
        
        Critères :
        - BPM : bon si écart < 10 BPM
        - Tonalité : bon si intervalle consonant
        - Énergie : bon si continuité
        - Genre : bon si compatible
        """
        score = 0.0

        # BPM (0-100 points)
        if track1.bpm and track2.bpm:
            bpm_diff = abs(track1.bpm - track2.bpm)
            if bpm_diff < 5:
                score += 100
            elif bpm_diff < 10:
                score += 80
            elif bpm_diff < 20:
                score += 50
            else:
                score += 20
        else:
            score += 30  # Fallback si BPM absent

        # Énergie (0-50 points)
        if track1.energy is not None and track2.energy is not None:
            energy_diff = abs(track1.energy - track2.energy)
            if energy_diff < 0.1:
                score += 50
            elif energy_diff < 0.3:
                score += 30
            else:
                score += 10
        else:
            score += 15

        # Tonalité (0-30 points) - intervalles consonants simplifiés
        if track1.key and track2.key:
            # Intervalles consonants : unisson, tierce, quinte, octave, etc.
            consonant_intervals = {
                0: 30,    # Unisson
                3: 25,    # Tierce mineure
                4: 25,    # Tierce majeure
                5: 28,    # Quarte
                7: 30,    # Quinte
                12: 30,   # Octave
            }
            interval = PlaylistManager._get_interval(track1.key, track2.key)
            score += consonant_intervals.get(interval, 5)
        else:
            score += 10

        # Genre (0-20 points)
        if track1.genre and track2.genre:
            if track1.genre == track2.genre:
                score += 20
            else:
                score += 5
        else:
            score += 8

        return score

    @staticmethod
    def _get_interval(key1: str, key2: str) -> int:
        """
        Calcule l'intervalle (en demi-tons) entre deux tonalités.
        
        Exemple: C → G = 7 (quinte)
        """
        notes = {
            "C": 0, "C#": 1, "Db": 1,
            "D": 2, "D#": 3, "Eb": 3,
            "E": 4, "F": 5,
            "F#": 6, "Gb": 6,
            "G": 7, "G#": 8, "Ab": 8,
            "A": 9, "A#": 10, "Bb": 10,
            "B": 11,
        }

        # Parser les clés (ex: "C", "D#", "Dm", "Cmaj7", etc.)
        note1_str = key1[0] if len(key1) > 0 else ""
        if len(key1) > 1 and key1[1] in "#b":
            note1_str = key1[:2]

        note2_str = key2[0] if len(key2) > 0 else ""
        if len(key2) > 1 and key2[1] in "#b":
            note2_str = key2[:2]

        n1 = notes.get(note1_str, 0)
        n2 = notes.get(note2_str, 0)

        interval = (n2 - n1) % 12
        return interval
