#!/usr/bin/env python3
"""SolarSound - Lecteur de musique 5.1 avec spatialisation avancée"""

import sys
import os
import tempfile
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QTimer

from core.qt_config import configure_qt_environment
try:
    from .core.error_logging import append_error_log
    from .core.single_instance import SingleInstanceServer
    from .video.player import ALL_MEDIA_FORMATS
except (ImportError, ModuleNotFoundError):
    from core.error_logging import append_error_log
    from core.single_instance import SingleInstanceServer
    from video.player import ALL_MEDIA_FORMATS

package_dir = os.path.dirname(os.path.abspath(__file__))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

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


def _supported_open_files(arguments):
    supported_extensions = set(ALL_MEDIA_FORMATS) | {".playlist"}
    return [
        arg for arg in arguments
        if os.path.isfile(arg)
        and os.path.splitext(arg)[1].lower() in supported_extensions
    ]


def main():
    startup_requested = "--startup" in sys.argv[1:]
    _fix_windows_taskbar_icon()
    configure_qt_environment()
    app = QApplication(sys.argv)
    app.setApplicationName("SolarSound")
    app.setOrganizationName("SolarSound")
    app.setStyle("Fusion")

    open_files = _supported_open_files(sys.argv[1:])
    instance_server = SingleInstanceServer(
        "SolarSound.SingleInstance",
        os.path.join(tempfile.gettempdir(), "SolarSound.SingleInstance.lock"),
    )
    try:
        if not instance_server.listen_or_forward(open_files):
            return
    except RuntimeError as exc:
        append_error_log(str(exc), "", context={"kind": "single_instance_error"})
        QMessageBox.critical(
            None,
            "SolarSound - Erreur",
            "Impossible de transmettre les fichiers à l'instance SolarSound déjà ouverte.",
        )
        return
    app.aboutToQuit.connect(instance_server.close)

    try:
        from .ui.main_window import MainWindow
        from .ui.splash_screen import SplashScreen
        from .core.session import SessionManager
    except (ImportError, ModuleNotFoundError):
        from ui.main_window import MainWindow
        from ui.splash_screen import SplashScreen
        from core.session import SessionManager

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

    splash.set_progress(15, "Preparation des composants audio...")
    app.processEvents()

    window = None
    window_ready = False
    pending_requests = []
    processing_open_files = False
    import_mode = None
    open_request_timer = QTimer(app)
    open_request_timer.setSingleShot(True)
    open_request_timer.setInterval(0)
    import_mode_timer = QTimer(app)
    import_mode_timer.setSingleShot(True)
    import_mode_timer.setInterval(30000)

    def reset_import_mode():
        nonlocal import_mode
        import_mode = None

    def enqueue_open_files(paths):
        if paths:
            pending_requests.extend(paths)
            open_request_timer.start()

    def process_open_files():
        nonlocal processing_open_files, import_mode
        if (
            window is None
            or not window_ready
            or processing_open_files
            or not pending_requests
        ):
            return
        processing_open_files = True
        paths = pending_requests[:]
        pending_requests.clear()
        try:
            if window.isMinimized() or not window.isVisible():
                window.show()
            window.raise_()
            window.activateWindow()
            if import_mode is None:
                import_mode = window._ask_import_playlist_mode()
            if import_mode is not None:
                mode = import_mode
                window._open_files_from_args(paths, playlist_mode=mode)
                if mode == "replace":
                    import_mode = "add"
                import_mode_timer.start()
        except Exception as exc:
            tb_txt = ''.join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
            append_error_log(str(exc), "", context={
                "kind": "open_files_exception",
                "traceback": tb_txt,
                "files": paths,
            })
            QMessageBox.critical(
                window,
                "SolarSound - Erreur",
                "Impossible d'ouvrir un ou plusieurs fichiers. "
                "Le journal d'erreurs a été mis à jour.",
            )
        finally:
            processing_open_files = False
            if pending_requests:
                open_request_timer.start()

    open_request_timer.timeout.connect(process_open_files)
    import_mode_timer.timeout.connect(reset_import_mode)
    instance_server.files_received.connect(enqueue_open_files)
    instance_server.request_error.connect(
        lambda message: append_error_log(
            message, "", context={"kind": "single_instance_request_error"}
        )
    )
    instance_server.queue_paths(open_files)

    def start_application():
        nonlocal window, window_ready
        try:
            window = MainWindow()
            if startup_requested and not open_files:
                window.start_configured_playback()
            _set_windows_window_icon(window, icon_path)
            splash.set_progress(82, "Finalisation de l'interface...")
            app.processEvents()
            splash.set_progress(100, "Pret")

            def finish_startup():
                nonlocal window_ready
                splash.finish(window)
                window_ready = True
                if pending_requests:
                    open_request_timer.start()
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
