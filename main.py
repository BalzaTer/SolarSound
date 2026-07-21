#!/usr/bin/env python3
"""SolarSound - Lecteur de musique 5.1 avec spatialisation avancée"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

package_dir = os.path.dirname(os.path.abspath(__file__))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

try:
    from .ui.main_window import MainWindow
except (ImportError, ModuleNotFoundError):
    from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SolarSound")
    app.setOrganizationName("SolarSound")
    app.setStyle("Fusion")

    # Fichiers passés en argument (via "Lire avec" ou glisser-déposer sur l'exe)
    # sys.argv[0] = chemin de l'exe, sys.argv[1:] = fichiers
    open_files = []
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            ext = os.path.splitext(arg)[1].lower()
            VIDEO_EXTS = (".mp4",".mkv",".avi",".mov",".wmv",".m4v",".flv",".webm")
            if ext in (".mp3", ".wav", ".playlist") or ext in VIDEO_EXTS:
                open_files.append(arg)

    window = MainWindow(open_files=open_files)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
