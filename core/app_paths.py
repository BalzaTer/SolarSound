"""Chemins des données persistantes de SolarSound."""

import os
import shutil
import sys


APP_NAME = "SolarSound"


def get_app_data_dir() -> str:
    """Retourne et crée le répertoire de données inscriptible de l'utilisateur."""
    if os.name == "nt":
        root = (
            os.environ.get("APPDATA")
            or os.environ.get("LOCALAPPDATA")
            or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
        )
    elif sys.platform == "darwin":
        root = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        root = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"
        )

    app_data_dir = os.path.join(root, APP_NAME)
    os.makedirs(app_data_dir, exist_ok=True)
    return app_data_dir


def get_legacy_app_data_dir() -> str:
    """Retourne l'ancien répertoire utilisé pour les données, près de l'application."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def migrate_legacy_file(
    filename: str, app_data_dir: str, legacy_dir: str | None = None
) -> None:
    """Copie un ancien fichier de données sans remplacer une version déjà migrée."""
    source = os.path.join(legacy_dir or get_legacy_app_data_dir(), filename)
    destination = os.path.join(app_data_dir, filename)
    if os.path.isfile(source) and not os.path.exists(destination):
        try:
            shutil.copy2(source, destination)
        except OSError as exc:
            print(f"[SolarSound] Migration impossible pour {source}: {exc}")


def migrate_legacy_directory(dirname: str, app_data_dir: str) -> None:
    """Copie les anciens fichiers d'un dossier sans écraser les données existantes."""
    source_dir = os.path.join(get_legacy_app_data_dir(), dirname)
    destination_dir = os.path.join(app_data_dir, dirname)
    if not os.path.isdir(source_dir):
        return

    os.makedirs(destination_dir, exist_ok=True)
    for filename in os.listdir(source_dir):
        source = os.path.join(source_dir, filename)
        destination = os.path.join(destination_dir, filename)
        if os.path.isfile(source) and not os.path.exists(destination):
            try:
                shutil.copy2(source, destination)
            except OSError as exc:
                print(f"[SolarSound] Migration impossible pour {source}: {exc}")
