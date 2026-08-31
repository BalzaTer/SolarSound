"""Gestion des covers d'images pour les playlists personnalisées"""

import os
import shutil
from typing import Optional
from pathlib import Path
import sys

try:
    from PIL import Image
except ImportError:
    Image = None


class CoverHandler:
    """Gère le redimensionnement et la persistance des covers de playlists"""

    TARGET_SIZE = (256, 256)  # Taille carrée cible
    COVERS_DIRNAME = "playlist_covers"

    def __init__(self, app_data_dir: str):
        """
        Initialise le gestionnaire de covers.
        
        Args:
            app_data_dir: Répertoire où stocker les covers (généralement à côté de l'exe)
        """
        self.app_data_dir = app_data_dir
        self.covers_dir = os.path.join(app_data_dir, self.COVERS_DIRNAME)
        self._ensure_covers_dir()

    def _ensure_covers_dir(self):
        """Crée le dossier playlist_covers s'il n'existe pas"""
        if not os.path.exists(self.covers_dir):
            try:
                os.makedirs(self.covers_dir, exist_ok=True)
            except Exception as e:
                print(f"[CoverHandler] Erreur création dossier covers: {e}")

    @staticmethod
    def _get_app_data_dir() -> str:
        """
        Détermine le répertoire de base pour les données app.
        - Exe PyInstaller : répertoire de l'exe
        - Script Python : répertoire racine (où est main.py)
        """
        if getattr(sys, "frozen", False):
            # Mode exe PyInstaller
            return os.path.dirname(sys.executable)
        else:
            # Mode script Python
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def save_cover(self, image_data: bytes, cover_name: str) -> Optional[str]:
        """
        Sauvegarde une image de cover redimensionnée en 256x256px carré.
        
        Args:
            image_data: Données binaires de l'image (JPG, PNG, etc.)
            cover_name: Nom du fichier de sortie (ex: "uuid.jpg")
            
        Returns:
            Chemin relatif au dossier covers (ex: "uuid.jpg") ou None si erreur
        """
        if not Image:
            print("[CoverHandler] PIL not available, cannot resize cover")
            return None

        try:
            # Créer image depuis bytes
            from io import BytesIO
            img = Image.open(BytesIO(image_data))
            
            # Convertir RGBA -> RGB si nécessaire
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = background
            
            # Redimensionner en carré 256x256 (center crop)
            img = self._resize_to_square(img, self.TARGET_SIZE)
            
            # Sauvegarder
            output_path = os.path.join(self.covers_dir, cover_name)
            img.save(output_path, "JPEG", quality=85)
            return cover_name
        except Exception as e:
            print(f"[CoverHandler] Erreur sauvegarde cover: {e}")
            return None

    def load_cover(self, cover_name: str) -> Optional[bytes]:
        """
        Charge une image de cover.
        
        Args:
            cover_name: Nom du fichier (ex: "uuid.jpg")
            
        Returns:
            Données binaires de l'image ou None si non trouvée
        """
        try:
            path = os.path.join(self.covers_dir, cover_name)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return f.read()
            return None
        except Exception as e:
            print(f"[CoverHandler] Erreur chargement cover: {e}")
            return None

    def load_cover_pixmap(self, cover_name: str):
        """
        Charge une image de cover comme QPixmap (PyQt6).
        
        Args:
            cover_name: Nom du fichier
            
        Returns:
            QPixmap ou None
        """
        try:
            from PyQt6.QtGui import QPixmap
            path = os.path.join(self.covers_dir, cover_name)
            if os.path.exists(path):
                return QPixmap(path)
            return None
        except Exception as e:
            print(f"[CoverHandler] Erreur chargement pixmap: {e}")
            return None

    def delete_cover(self, cover_name: str) -> bool:
        """
        Supprime une image de cover.
        
        Args:
            cover_name: Nom du fichier
            
        Returns:
            True si supprimé, False sinon
        """
        try:
            path = os.path.join(self.covers_dir, cover_name)
            if os.path.exists(path):
                os.remove(path)
                return True
            return False
        except Exception as e:
            print(f"[CoverHandler] Erreur suppression cover: {e}")
            return False

    def import_cover_from_file(self, source_path: str, cover_name: str) -> Optional[str]:
        """
        Importe un fichier image et le redimensionne en cover.
        
        Args:
            source_path: Chemin de l'image source
            cover_name: Nom du cover à créer
            
        Returns:
            Nom du cover créé ou None
        """
        try:
            if not os.path.exists(source_path):
                return None
            with open(source_path, "rb") as f:
                data = f.read()
            return self.save_cover(data, cover_name)
        except Exception as e:
            print(f"[CoverHandler] Erreur import cover: {e}")
            return None

    @staticmethod
    def _resize_to_square(img, size: tuple) -> 'Image':
        """
        Redimensionne une image en carré avec center crop.
        
        Args:
            img: Image PIL
            size: Tuple (width, height)
            
        Returns:
            Image PIL redimensionnée et centrée
        """
        width, height = img.size
        min_dim = min(width, height)
        
        # Crop au carré (center)
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim
        img = img.crop((left, top, right, bottom))
        
        # Resize to target
        img = img.resize(size, Image.Resampling.LANCZOS)
        return img
