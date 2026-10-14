"""
Asynchronous audio excerpts for search-result hover previews.

Decoding is done on a worker thread so hovering a result never blocks the UI.
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

try:
    import sounddevice as sd
    SOUNDDEVICE_OK = True
except Exception:
    SOUNDDEVICE_OK = False

try:
    from .engine import decode_audio_excerpt
except (ImportError, ModuleNotFoundError):
    from audio.engine import decode_audio_excerpt


class _PreviewDecodeWorker(QThread):
    decoded = pyqtSignal(int, object, int)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, path: str, excerpt_seconds: float):
        super().__init__()
        self.request_id = request_id
        self.path = path
        self.excerpt_seconds = excerpt_seconds

    def run(self):
        try:
            data, sample_rate = decode_audio_excerpt(
                self.path, self.excerpt_seconds
            )
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(self.request_id, str(exc))
            return
        if not self.isInterruptionRequested():
            self.decoded.emit(self.request_id, data, sample_rate)


class PreviewPlayer(QObject):
    """
    Plays a short centered excerpt independently of the main audio engine.

    Decoding happens asynchronously; `excerpt_started` and `excerpt_failed`
    report its eventual outcome.
    """

    excerpt_started = pyqtSignal(float)
    excerpt_failed = pyqtSignal(str)

    def __init__(self, excerpt_seconds: float = 6.0, parent=None):
        super().__init__(parent)
        self.excerpt_seconds = excerpt_seconds
        self._current_path = None
        self._request_id = 0
        self._worker = None
        self._pending_request = None

    def play_excerpt(self, path: str):
        """Queue decoding and playback of a centered excerpt for this file."""
        self.stop()
        self._current_path = path
        if not SOUNDDEVICE_OK:
            self.excerpt_failed.emit("sounddevice indisponible")
            return

        self._request_id += 1
        request = (self._request_id, path)
        if self._worker is not None and self._worker.isRunning():
            self._pending_request = request
            self._worker.requestInterruption()
            return
        self._start_worker(*request)

    def stop(self):
        """Stop playback and invalidate any in-flight decode request."""
        self._request_id += 1
        self._pending_request = None
        self._current_path = None
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
        if SOUNDDEVICE_OK:
            try:
                sd.stop()
            except Exception:
                pass

    def shutdown(self):
        """Wait for an in-flight decoder before destroying its owner."""
        self.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait()

    def _start_worker(self, request_id: int, path: str):
        worker = _PreviewDecodeWorker(
            request_id, path, self.excerpt_seconds
        )
        worker.decoded.connect(self._on_decoded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    @pyqtSlot(int, object, int)
    def _on_decoded(self, request_id: int, data, sample_rate: int):
        if request_id != self._request_id or self._current_path is None:
            return
        if len(data) == 0:
            self._on_failed(request_id, "L'extrait audio est vide.")
            return
        try:
            excerpt = data.astype("float32") / 32768.0
            duration = len(excerpt) / float(sample_rate)
            sd.play(excerpt, sample_rate)
        except Exception as exc:
            self._on_failed(request_id, str(exc))
            return
        self.excerpt_started.emit(duration)

    @pyqtSlot(int, str)
    def _on_failed(self, request_id: int, message: str):
        if request_id != self._request_id:
            return
        self._current_path = None
        self.excerpt_failed.emit(message)

    @pyqtSlot()
    def _on_worker_finished(self):
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
        worker.deleteLater()
        if self._pending_request is not None:
            request = self._pending_request
            self._pending_request = None
            self._start_worker(*request)
