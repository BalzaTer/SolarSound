"""Gestionnaire central des playlists personnalisées"""

import json
import os
import sys
import shutil
from typing import List, Optional
from datetime import datetime

try:
    from .custom_playlist import (
        CustomPlaylist, CustomTrack, PlaylistLibrary,
        PlaylistFolder, MoodEnum
    )
    from .cover_handler import CoverHandler
except (ImportError, ModuleNotFoundError):
    from custom_playlist import (
        CustomPlaylist, CustomTrack, PlaylistLibrary,
        PlaylistFolder, MoodEnum
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

    def backup_to(self, destination_path: str) -> bool:
        """
        Sauvegarde une copie du JSON de toutes les playlists vers un chemin
        choisi par l'utilisateur (bouton "Sauvegarder toutes les playlists").
        S'assure d'abord que le fichier sur disque est à jour.

        Returns:
            True si succès, False sinon
        """
        if not self.save_all():
            return False
        try:
            shutil.copyfile(self.playlists_path, destination_path)
            return True
        except Exception as e:
            print(f"[PlaylistManager] Erreur sauvegarde copie: {e}")
            return False

    def relocate_missing_tracks(self, library_folders: List[str], report=None) -> dict:
        """
        Parcourt toutes les playlists personnalisées, repère les pistes dont
        le fichier n'existe plus à son emplacement d'origine, et tente de
        les retrouver dans les dossiers de musique configurés (par taille de
        fichier + durée, puis par titre/artiste en repli).

        Args:
            report: callback optionnel `report(current, total, message)`

        Returns:
            dict avec : checked (pistes vérifiées), missing (introuvables au
            départ), relocated (retrouvées et corrigées), still_missing
            (liste de (nom_playlist, titre_piste) non retrouvées)
        """
        from .library_scanner import scan_library_folders, find_replacement_for_track

        index = scan_library_folders(library_folders, report=report)

        checked = 0
        missing = 0
        relocated = 0
        still_missing = []

        all_pairs = [(pl, t) for pl in self.library.playlists for t in pl.tracks]
        total = len(all_pairs)
        if report:
            report(0, total, "Vérification des pistes…")

        for i, (playlist, track) in enumerate(all_pairs, start=1):
            checked += 1
            if os.path.exists(track.path):
                continue
            missing += 1
            match = find_replacement_for_track(track, index)
            if match:
                track.path = match["path"]
                if not track.file_size:
                    track.file_size = match.get("size")
                relocated += 1
            else:
                still_missing.append((playlist.name, track.title))
            if report and (i % 3 == 0 or i == total):
                report(i, total, f"Vérification des pistes… ({i}/{total})")

        if relocated:
            self.save_all()

        return {
            "checked": checked,
            "missing": missing,
            "relocated": relocated,
            "still_missing": still_missing,
        }

    # ── CRUD Playlists ──────────────────────────────────────────────

    def create_playlist(self, name: str, moods: Optional[List[str]] = None,
                         folder_id: Optional[str] = None) -> CustomPlaylist:
        """
        Crée une nouvelle playlist.
        
        Args:
            name: Nom de la playlist
            moods: Liste optionnelle d'humeurs
            folder_id: Dossier dans lequel créer la playlist (None = racine)
            
        Returns:
            Playlist créée
        """
        playlist = CustomPlaylist(name=name, folder_id=folder_id)
        if moods:
            playlist.set_moods(moods)
        playlist.order = self._next_order_in_scope(folder_id)
        self.library.add_playlist(playlist)
        self.save_all()
        return playlist

    def _next_order_in_scope(self, folder_id: Optional[str]) -> int:
        """Retourne la prochaine position libre (fin de liste) dans un dossier (ou la racine)"""
        siblings = [p for p in self.library.playlists if p.folder_id == folder_id]
        return len(siblings)

    def duplicate_playlist(self, playlist_id: str) -> Optional[CustomPlaylist]:
        """
        Duplique une playlist (nom, humeurs, pistes et cover), placée à la
        suite de l'originale dans le même dossier.

        Returns:
            La nouvelle playlist créée, ou None si l'originale est introuvable
        """
        original = self.get_playlist(playlist_id)
        if not original:
            return None

        new_playlist = CustomPlaylist(
            name=f"{original.name} (copie)",
            moods=list(original.moods),
            folder_id=original.folder_id,
            tracks=[CustomTrack.from_dict(t.to_dict()) for t in original.tracks],
        )

        if original.cover_path:
            new_cover_name = f"{new_playlist.id}.jpg"
            copied = self.cover_handler.duplicate_cover(original.cover_path, new_cover_name)
            if copied:
                new_playlist.cover_path = copied

        new_playlist.order = self._next_order_in_scope(original.folder_id)
        self.library.add_playlist(new_playlist)
        self.save_all()
        return new_playlist

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

    # ── Organisation : dossiers, ordre, déplacement ──────────────────

    def create_folder(self, name: str) -> PlaylistFolder:
        """Crée un dossier pour organiser les playlists (à la racine)"""
        folder = PlaylistFolder(name=name)
        folder.order = len(self.library.folders)
        self.library.add_folder(folder)
        self.save_all()
        return folder

    def rename_folder(self, folder_id: str, name: str) -> bool:
        """Renomme un dossier"""
        folder = self.library.get_folder(folder_id)
        if not folder:
            return False
        folder.name = name
        self.save_all()
        return True

    def delete_folder(self, folder_id: str) -> bool:
        """
        Supprime un dossier. Les playlists qu'il contenait sont remontées
        à la racine (elles ne sont jamais supprimées avec le dossier).
        """
        folder = self.library.get_folder(folder_id)
        if not folder:
            return False

        root_order = self._next_order_in_scope(None)
        for playlist in self.library.playlists:
            if playlist.folder_id == folder_id:
                playlist.folder_id = None
                playlist.order = root_order
                root_order += 1

        self.library.remove_folder(folder_id)
        self.save_all()
        return True

    def get_all_folders(self) -> List[PlaylistFolder]:
        """Retourne tous les dossiers"""
        return self.library.get_all_folders()

    def get_folder(self, folder_id: str) -> Optional[PlaylistFolder]:
        """Récupère un dossier par ID"""
        return self.library.get_folder(folder_id)

    def move_playlist_to_folder(self, playlist_id: str, folder_id: Optional[str]) -> bool:
        """Déplace une playlist vers un dossier (None = racine), en fin de liste"""
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False
        if folder_id is not None and not self.library.get_folder(folder_id):
            return False
        playlist.folder_id = folder_id
        playlist.order = self._next_order_in_scope(folder_id)
        playlist.modified_at = datetime.now().isoformat()
        self.save_all()
        return True

    def move_playlist_step(self, playlist_id: str, direction: str) -> bool:
        """
        Déplace une playlist d'un cran vers le haut ou le bas au sein de
        son dossier (ou de la racine).

        Args:
            direction: "up" ou "down"
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False

        siblings = sorted(
            [p for p in self.library.playlists if p.folder_id == playlist.folder_id],
            key=lambda p: p.order,
        )
        idx = next((i for i, p in enumerate(siblings) if p.id == playlist_id), None)
        if idx is None:
            return False

        target_idx = idx - 1 if direction == "up" else idx + 1
        if target_idx < 0 or target_idx >= len(siblings):
            return False

        siblings[idx], siblings[target_idx] = siblings[target_idx], siblings[idx]
        for i, p in enumerate(siblings):
            p.order = i
        self.save_all()
        return True

    def move_folder_step(self, folder_id: str, direction: str) -> bool:
        """Déplace un dossier d'un cran vers le haut ou le bas parmi les autres dossiers"""
        folders = sorted(self.library.folders, key=lambda f: f.order)
        idx = next((i for i, f in enumerate(folders) if f.id == folder_id), None)
        if idx is None:
            return False

        target_idx = idx - 1 if direction == "up" else idx + 1
        if target_idx < 0 or target_idx >= len(folders):
            return False

        folders[idx], folders[target_idx] = folders[target_idx], folders[idx]
        for i, f in enumerate(folders):
            f.order = i
        self.save_all()
        return True

    def set_playlist_position(self, playlist_id: str, folder_id: Optional[str], order: int):
        """
        Fixe directement le dossier et la position d'une playlist, sans
        sauvegarder (utilisé pour reconstruire l'ordre complet après un
        glisser-déposer dans l'arbre ; l'appelant doit ensuite appeler
        save_all() une seule fois).
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False
        playlist.folder_id = folder_id
        playlist.order = order
        playlist.modified_at = datetime.now().isoformat()
        return True

    def set_folder_position(self, folder_id: str, order: int):
        """Fixe directement la position d'un dossier, sans sauvegarder (voir set_playlist_position)"""
        folder = self.library.get_folder(folder_id)
        if not folder:
            return False
        folder.order = order
        return True

    def set_folder_expanded(self, folder_id: str, expanded: bool) -> bool:
        """Mémorise l'état plié/déplié d'un dossier (persisté entre les sessions)"""
        folder = self.library.get_folder(folder_id)
        if not folder:
            return False
        if folder.expanded == expanded:
            return True
        folder.expanded = expanded
        self.save_all()
        return True

    # ── Gestion des pistes ──────────────────────────────────────────

    def add_tracks_to_playlist(self, playlist_id: str, file_paths: List[str], report=None) -> int:
        """
        Ajoute des fichiers audio à une playlist.
        
        Args:
            playlist_id: ID de la playlist
            file_paths: Liste de chemins fichiers
            report: callback optionnel `report(current, total, message)`
            
        Returns:
            Nombre de pistes ajoutées
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return 0

        tracks = self._build_tracks_from_paths(file_paths, report=report)
        if tracks:
            playlist.add_tracks(tracks)
            self.save_all()
        return len(tracks)

    def _build_tracks_from_paths(self, file_paths: List[str], report=None) -> List[CustomTrack]:
        """
        Construit des CustomTrack depuis une liste de chemins, avec extraction
        des métadonnées (titre/artiste/durée + bpm/tonalité/énergie/genre pour le Flow).
        Ne touche pas au disque (pas de sauvegarde) — utilisé en interne.
        """
        from core.playlist import Playlist
        from audio.metadata import read_metadata
        from audio.audio_analysis import extract_audio_metadata
        supported = set(Playlist.SUPPORTED_FORMATS + Playlist.SUPPORTED_VIDEO_FORMATS)

        valid_paths = [
            p for p in file_paths
            if os.path.exists(p) and os.path.splitext(p)[1].lower() in supported
        ]
        total = len(valid_paths)

        tracks = []
        for i, path in enumerate(valid_paths, start=1):
            info = read_metadata(path)
            audio_meta = extract_audio_metadata(path)
            try:
                file_size = os.path.getsize(path)
            except OSError:
                file_size = None
            tracks.append(CustomTrack(
                path=path,
                title=info.get("title", ""),
                artist=info.get("artist", ""),
                album=info.get("album", ""),
                duration=audio_meta.get("duration") or info.get("duration", 0.0),
                bpm=audio_meta.get("bpm"),
                key=audio_meta.get("key"),
                energy=audio_meta.get("energy"),
                genre=audio_meta.get("genre"),
                file_size=file_size,
            ))
            if report and (i % 3 == 0 or i == total):
                report(i, total, f"Ajout des pistes… ({i}/{total}) {os.path.basename(path)}")
        return tracks

    def add_folder_to_playlist(self, playlist_id: str, folder_path: str, report=None) -> int:
        """
        Ajoute tous les fichiers d'un dossier (récursivement) à une playlist.
        
        Args:
            playlist_id: ID de la playlist
            folder_path: Chemin du dossier
            report: callback optionnel `report(current, total, message)`
            
        Returns:
            Nombre de pistes ajoutées
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist or not os.path.isdir(folder_path):
            return 0

        from core.playlist import Playlist
        supported = set(Playlist.SUPPORTED_FORMATS + Playlist.SUPPORTED_VIDEO_FORMATS)

        if report:
            report(0, 0, f"Recherche des fichiers dans {os.path.basename(folder_path)}…")

        file_paths = []
        for root, _, files in os.walk(folder_path):
            for file in sorted(files):
                ext = os.path.splitext(file)[1].lower()
                if ext in supported:
                    file_paths.append(os.path.join(root, file))

        tracks = self._build_tracks_from_paths(file_paths, report=report)
        if tracks:
            playlist.add_tracks(tracks)
            self.save_all()
        return len(tracks)

    def create_playlists_from_folders(self, folder_paths: List[str],
                                       target_folder_id: Optional[str] = None,
                                       report=None) -> List[CustomPlaylist]:
        """
        Crée une playlist par dossier fourni (nommée d'après le dossier),
        remplie récursivement avec les fichiers AUDIO trouvés dans ce dossier
        et ses sous-dossiers. Permet de glisser-déposer plusieurs dossiers
        adjacents d'un coup : une playlist est créée pour chacun.

        Args:
            folder_paths: Chemins des dossiers déposés
            target_folder_id: Dossier "Mes Playlists" dans lequel ranger les
                               nouvelles playlists créées (None = racine)
            report: callback optionnel `report(current, total, message)`
                    (progression au niveau des dossiers traités)

        Returns:
            Liste des playlists créées (les dossiers vides ou sans fichier
            audio ne créent pas de playlist)
        """
        from core.playlist import Playlist

        total_folders = len(folder_paths)
        created = []
        for folder_index, folder_path in enumerate(folder_paths, start=1):
            if not os.path.isdir(folder_path):
                continue

            folder_name = os.path.basename(os.path.normpath(folder_path)) or folder_path
            if report:
                report(folder_index - 1, total_folders,
                       f"Dossier {folder_index}/{total_folders} : {folder_name}…")

            file_paths = []
            for root, _, files in os.walk(folder_path):
                for f in sorted(files):
                    ext = os.path.splitext(f)[1].lower()
                    if ext in Playlist.SUPPORTED_FORMATS:
                        file_paths.append(os.path.join(root, f))

            if not file_paths:
                continue

            def _sub_report(i, n, msg, _folder_name=folder_name,
                             _folder_index=folder_index, _total_folders=total_folders):
                if report:
                    report(_folder_index - 1, _total_folders,
                           f"Dossier {_folder_index}/{_total_folders} : {_folder_name} ({i}/{n})")

            tracks = self._build_tracks_from_paths(file_paths, report=_sub_report)
            if not tracks:
                continue

            playlist = CustomPlaylist(name=folder_name, folder_id=target_folder_id, tracks=tracks)
            playlist.order = self._next_order_in_scope(target_folder_id)
            self.library.add_playlist(playlist)
            created.append(playlist)

            if report:
                report(folder_index, total_folders,
                       f"Dossier {folder_index}/{total_folders} : {folder_name} terminé")

        if created:
            self.save_all()
        return created

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
