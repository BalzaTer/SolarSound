"""
Lecteur d'extraits en arrière-plan, pour l'aperçu au survol des résultats de
recherche. Totalement indépendant du lecteur principal (AudioEngine) : ne
touche jamais à la playlist affichée, à la piste "en cours de lecture", ni à
aucun affichage de l'interface. Sert uniquement à donner une idée rapide du
morceau pendant que l'utilisateur survole un résultat.
"""

import numpy as np

try:
    import sounddevice as sd
    SOUNDDEVICE_OK = True
except Exception:
    SOUNDDEVICE_OK = False

try:
    from .engine import decode_audio_file
except (ImportError, ModuleNotFoundError):
    from audio.engine import decode_audio_file


class PreviewPlayer:
    """
    Joue un court extrait (par défaut : les quelques secondes au milieu du
    fichier) d'une piste, en arrière-plan, sans jamais passer par le
    lecteur principal de l'application.
    """

    def __init__(self, excerpt_seconds: float = 6.0):
        self.excerpt_seconds = excerpt_seconds
        self._current_path = None

    def play_excerpt(self, path: str) -> float:
        """
        Lance (ou remplace) l'extrait en cours pour ce fichier.
        Retourne sa durée en secondes (0.0 si rien n'a pu être joué), pour
        que l'appelant puisse programmer la reprise du lecteur principal
        une fois l'extrait terminé.
        """
        if not SOUNDDEVICE_OK:
            return 0.0
        self.stop()
        self._current_path = path
        try:
            data, sr = decode_audio_file(path)
        except Exception as e:
            print(f"[PreviewPlayer] Impossible de décoder l'extrait de {path} : {e}")
            self._current_path = None
            return 0.0

        total_frames = len(data)
        if total_frames <= 0:
            return 0.0

        excerpt_frames = int(self.excerpt_seconds * sr)
        start = max(0, total_frames // 2 - excerpt_frames // 2)
        end = min(total_frames, start + excerpt_frames)
        if end <= start:
            return 0.0

        excerpt = data[start:end].astype(np.float32) / 32768.0
        duration = len(excerpt) / float(sr)

        try:
            sd.play(excerpt, sr)
            return duration
        except Exception as e:
            print(f"[PreviewPlayer] Impossible de jouer l'extrait de {path} : {e}")
            self._current_path = None
            return 0.0

    def stop(self):
        """Arrête l'extrait en cours, s'il y en a un."""
        if not SOUNDDEVICE_OK:
            return
        try:
            sd.stop()
        except Exception:
            pass
        self._current_path = None
