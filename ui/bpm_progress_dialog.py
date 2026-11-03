"""Progression et contrôle des traitements d'analyse BPM."""

import threading

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
)

try:
    from ..audio.bpm_tagging import find_audio_files, process_bpm_files
except (ImportError, ModuleNotFoundError):
    from audio.bpm_tagging import find_audio_files, process_bpm_files


class BpmTaggingWorker(QThread):
    progress = pyqtSignal(int, int, str)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        paths,
        replace_existing,
        folders=None,
        supported_extensions=None,
    ):
        super().__init__()
        self._paths = paths
        self._replace_existing = replace_existing
        self._folders = folders
        self._supported_extensions = supported_extensions
        self._stop_requested = threading.Event()
        self._rollback_requested = threading.Event()

    def request_stop(self, rollback):
        if rollback:
            self._rollback_requested.set()
        self._stop_requested.set()

    def run(self):
        try:
            paths = self._paths
            discovery_errors = []
            if self._folders is not None:
                paths, discovery_errors, stopped = find_audio_files(
                    self._folders,
                    self._supported_extensions,
                    report=self.progress.emit,
                    should_stop=self._stop_requested.is_set,
                )
                if stopped:
                    self.completed.emit({
                        "written": {},
                        "skipped": 0,
                        "errors": discovery_errors,
                        "stopped": True,
                        "rolled_back": self._rollback_requested.is_set(),
                        "restored": 0,
                    })
                    return
                self.progress.emit(
                    0,
                    len(paths),
                    f"{len(paths)} fichier(s) trouvé(s), démarrage de l'analyse…",
                )
            result = process_bpm_files(
                paths,
                self._replace_existing,
                report=self.progress.emit,
                should_stop=self._stop_requested.is_set,
                rollback_on_stop=self._rollback_requested.is_set,
            )
            result["errors"] = discovery_errors + result["errors"]
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(result)


class BpmProgressDialog(QDialog):
    """Dialog modal avec annulation transactionnelle ou arrêt conservé."""

    def __init__(
        self,
        paths,
        replace_existing,
        parent=None,
        folders=None,
        supported_extensions=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Analyse et inscription des BPM")
        self.setMinimumWidth(500)
        self.setModal(True)
        self.result_data = None
        self.error_message = ""
        self._finished = False

        layout = QVBoxLayout(self)
        message = (
            "Recherche des fichiers audio dans les dossiers configurés…"
            if folders is not None
            else f"Préparation de l'analyse de {len(paths)} fichier(s)…"
        )
        self.lbl_message = QLabel(message)
        self.lbl_message.setWordWrap(True)
        layout.addWidget(self.lbl_message)

        self.progress_bar = QProgressBar()
        if folders is not None:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, len(paths))
        layout.addWidget(self.progress_bar)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.btn_cancel = QPushButton("Annuler et restaurer")
        self.btn_close = QPushButton("Fermer et conserver")
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_close)
        layout.addLayout(buttons)

        self._worker = BpmTaggingWorker(
            paths,
            replace_existing,
            folders,
            supported_extensions,
        )
        self._worker.progress.connect(self._update_progress)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self.btn_cancel.clicked.connect(lambda: self._request_stop(rollback=True))
        self.btn_close.clicked.connect(lambda: self._request_stop(rollback=False))
        self._worker.start()

    def _update_progress(self, current, total, message):
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
        else:
            self.progress_bar.setRange(0, 0)
        self.lbl_message.setText(message)

    def _request_stop(self, rollback):
        if self._finished:
            self.accept()
            return
        self.btn_cancel.setEnabled(False)
        self.btn_close.setEnabled(False)
        self._worker.request_stop(rollback)
        if rollback:
            self.lbl_message.setText(
                "Annulation en cours : restauration des fichiers modifiés…"
            )
        else:
            self.lbl_message.setText(
                "Arrêt en cours : les modifications déjà effectuées seront conservées…"
            )

    def _on_completed(self, result):
        self._finished = True
        self.result_data = result
        self.accept()

    def _on_failed(self, message):
        self._finished = True
        self.error_message = message
        self.accept()

    def closeEvent(self, event):
        if self._finished:
            event.accept()
        else:
            self._request_stop(rollback=False)
            event.ignore()

    def reject(self):
        if self._finished:
            super().reject()
        else:
            self._request_stop(rollback=False)


def run_bpm_tagging(parent, paths, replace_existing):
    dialog = BpmProgressDialog(paths, replace_existing, parent)
    dialog.exec()
    dialog._worker.wait()
    return dialog.result_data, dialog.error_message


def run_bpm_tagging_in_folders(
    parent,
    folders,
    supported_extensions,
    replace_existing,
):
    dialog = BpmProgressDialog(
        [],
        replace_existing,
        parent,
        folders=folders,
        supported_extensions=supported_extensions,
    )
    dialog.exec()
    dialog._worker.wait()
    return dialog.result_data, dialog.error_message
