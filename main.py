#!/usr/bin/env python3
"""SolarSound - Lecteur de musique 5.1 avec spatialisation avancée"""

import sys
import os
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer

from core.qt_config import configure_qt_environment
try:
    from .core.error_logging import append_error_log
except (ImportError, ModuleNotFoundError):
    from core.error_logging import append_error_log

package_dir = os.path.dirname(os.path.abspath(__file__))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

try:
    from .ui.main_window import MainWindow
    from .ui.splash_screen import SplashScreen
    from .core.session import SessionManager
except (ImportError, ModuleNotFoundError):
    from ui.main_window import MainWindow
    from ui.splash_screen import SplashScreen
    from core.session import SessionManager


def main():
    configure_qt_environment()
    app = QApplication(sys.argv)
    app.setApplicationName("SolarSound")
    app.setOrganizationName("SolarSound")
    app.setStyle("Fusion")

    logo_path = os.path.join(package_dir, "icons", "logo.png")
    splash = SplashScreen(logo_path)
    splash.show()
    startup_session = SessionManager().load()
    screens = QApplication.screens()
    target_screen = next(
        (screen for screen in screens if screen.name() == startup_session.window.screen_name),
        screens[0] if screens else None,
    )
    splash.center_on_screen(target_screen)
    app.processEvents()

    # Fichiers passés en argument (via "Lire avec" ou glisser-déposer sur l'exe)
    # sys.argv[0] = chemin de l'exe, sys.argv[1:] = fichiers
    open_files = []
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            ext = os.path.splitext(arg)[1].lower()
            VIDEO_EXTS = (".mp4",".mkv",".avi",".mov",".wmv",".m4v",".flv",".webm")
            AUDIO_EXTS = (".mp3", ".wav", ".flac", ".ogg", ".opus", ".aiff", ".aif", ".au", ".rf64", ".w64")
            if ext in AUDIO_EXTS or ext == ".playlist" or ext in VIDEO_EXTS:
                open_files.append(arg)

    splash.set_progress(15, "Preparation des composants audio...")
    app.processEvents()

    def start_application():
        try:
            window = MainWindow(open_files=open_files)
            splash.set_progress(82, "Finalisation de l'interface...")
            app.processEvents()
            splash.set_progress(100, "Pret")
            QTimer.singleShot(220, lambda: splash.finish(window))
        except Exception as exc:
            tb_txt = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            append_error_log(str(exc), "", context={
                "kind": "startup_exception",
                "traceback": tb_txt,
            })
            splash.close()
            QMessageBox.critical(
                None,
                "SolarSound - Erreur",
                "Impossible de demarrer SolarSound. Le log a ete enregistre.",
            )
            app.quit()

    # Laisser le splash s'afficher et son animation demarrer avant le travail lourd.
    QTimer.singleShot(120, start_application)

    try:
        sys.exit(app.exec())
    except Exception as exc:
        tb_txt = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        append_error_log(str(exc), "", context={
            "kind": "uncaught_exception",
            "traceback": tb_txt,
        })
        QMessageBox.critical(None, "SolarSound - Erreur",
            "Une erreur inattendue est survenue. Le log a été enregistré dans playback_errors.log.")
        raise


if __name__ == "__main__":
    main()
