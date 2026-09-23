#!/usr/bin/env python3
"""SolarSound - Lecteur de musique 5.1 avec spatialisation avancée"""

import sys
import os
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
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


def _fix_windows_taskbar_icon():
    """
    Sans ceci, Windows regroupe le processus sous l'identité de son
    exécutable hôte (python.exe/pythonw.exe, ou le bootloader PyInstaller
    en mode onefile) plutôt que sous une identité propre à SolarSound.
    Résultat : l'icône de la barre des tâches reste celle de l'exécutable
    hôte (générique, ou absente) tant que Windows n'a pas, par hasard,
    une raison de rafraîchir le bouton — ce qui explique qu'elle
    "apparaisse" après coup (ex. au lancement d'une première lecture,
    qui déclenche des changements d'état de fenêtre).

    Doit être appelé AVANT la création de la QApplication / de toute
    fenêtre, car Windows fige cette identité dès la première fenêtre
    affichée.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "SolarSound.MusicPlayer.1"
        )
    except Exception:
        pass


def _set_windows_window_icon(window, icon_path):
    """Force l'icône native de la fenêtre, notamment pour la barre des tâches."""
    if os.name != "nt" or not os.path.isfile(icon_path):
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        load_image = user32.LoadImageW
        load_image.restype = ctypes.c_void_p
        hicon = load_image(None, icon_path, 1, 0, 0, 0x00000010 | 0x00000040)
        if hicon:
            hwnd = int(window.winId())
            user32.SendMessageW(hwnd, 0x0080, 0, hicon)
            user32.SendMessageW(hwnd, 0x0080, 1, hicon)
    except Exception:
        pass


def main():
    startup_requested = "--startup" in sys.argv[1:]
    _fix_windows_taskbar_icon()
    configure_qt_environment()
    app = QApplication(sys.argv)
    app.setApplicationName("SolarSound")
    app.setOrganizationName("SolarSound")
    app.setStyle("Fusion")

    # Icône par défaut pour toutes les fenêtres du processus (fallback
    # avant même que MainWindow ne pose la sienne) ; contribue aussi à ce
    # que Windows associe la bonne icône dès la 1re fenêtre affichée.
    icon_path = os.path.join(package_dir, "icons", "solarsound.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    logo_path = os.path.join(package_dir, "icons", "logo.png")
    splash = SplashScreen(logo_path)
    splash.setWindowIcon(QIcon(icon_path))
    splash.show()
    _set_windows_window_icon(splash, icon_path)
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
            if startup_requested:
                window.start_configured_playback()
            _set_windows_window_icon(window, icon_path)
            splash.set_progress(82, "Finalisation de l'interface...")
            app.processEvents()
            splash.set_progress(100, "Pret")

            def finish_startup():
                splash.finish(window)
                # Windows cree le bouton de barre des taches apres l'affichage.
                # Reappliquer l'icone une fois ce bouton effectivement present.
                QTimer.singleShot(
                    200,
                    lambda: _set_windows_window_icon(window, icon_path),
                )

            QTimer.singleShot(220, finish_startup)
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
