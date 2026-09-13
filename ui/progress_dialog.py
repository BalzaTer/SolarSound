"""
Fenêtre de progression générique pour les tâches un peu longues (scan de
dossiers, import de musique, recherche de fichiers déplacés...), exécutées
en arrière-plan pour ne jamais geler l'interface.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class TaskWorker(QThread):
    """
    Exécute une fonction longue durée dans un thread séparé.

    La fonction cible doit accepter un argument nommé `report` (callable) :
    elle peut l'appeler régulièrement avec `report(current, total, message)`
    pour signaler sa progression (total=0 → progression indéterminée).
    """

    progress = pyqtSignal(int, int, str)
    finished_with_result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        def report(current, total, message=""):
            self.progress.emit(current, total, message)

        try:
            result = self._func(*self._args, report=report, **self._kwargs)
            self.finished_with_result.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class ProgressDialog(QDialog):
    """Fenêtre simple : titre, message d'état, barre de progression."""

    def __init__(self, title: str, initial_message: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setModal(True)
        self.setWindowFlags(
            (self.windowFlags() | Qt.WindowType.CustomizeWindowHint)
            & ~Qt.WindowType.WindowCloseButtonHint
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        self.lbl_message = QLabel(initial_message)
        self.lbl_message.setWordWrap(True)
        layout.addWidget(self.lbl_message)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indéterminé tant qu'on n'a pas de total
        layout.addWidget(self.progress_bar)

    def update_progress(self, current: int, total: int, message: str):
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
        else:
            self.progress_bar.setRange(0, 0)
        if message:
            self.lbl_message.setText(message)


def run_with_progress(parent, title: str, initial_message: str, func,
                       on_success=None, on_error=None, *args, **kwargs):
    """
    Lance `func` en arrière-plan avec une fenêtre de progression, et appelle
    `on_success(result)` ou `on_error(message)` une fois terminé (sur le
    thread principal). Garde une référence au worker sur le dialogue lui-même
    pour éviter qu'il ne soit détruit prématurément par le ramasse-miettes.
    """
    dialog = ProgressDialog(title, initial_message, parent)
    worker = TaskWorker(func, *args, **kwargs)
    dialog._worker = worker  # évite le garbage collection pendant l'exécution

    worker.progress.connect(dialog.update_progress)

    def _on_finished(result):
        dialog.accept()
        if on_success:
            on_success(result)

    def _on_failed(message):
        dialog.reject()
        if on_error:
            on_error(message)

    worker.finished_with_result.connect(_on_finished)
    worker.failed.connect(_on_failed)

    worker.start()
    dialog.exec()
