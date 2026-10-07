"""Single-instance forwarding for desktop file-open requests."""

import json
import os

from PyQt6.QtCore import QObject, QLockFile, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstanceServer(QObject):
    files_received = pyqtSignal(list)
    request_error = pyqtSignal(str)
    FILE_BATCH_DELAY_MS = 750

    def __init__(self, server_name: str, lock_path: str, parent=None):
        super().__init__(parent)
        self.server_name = server_name
        self._lock = QLockFile(lock_path)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept_connections)
        self._buffers = {}
        self._pending_paths = []
        self._batch_timer = QTimer(self)
        self._batch_timer.setSingleShot(True)
        self._batch_timer.setInterval(self.FILE_BATCH_DELAY_MS)
        self._batch_timer.timeout.connect(self._emit_pending_paths)

    def queue_paths(self, paths: list[str]):
        """Combine nearby open requests, as Windows may launch once per file."""
        if not paths:
            return
        self._pending_paths.extend(paths)
        self._batch_timer.start()

    def listen_or_forward(self, paths: list[str]) -> bool:
        """Listen as the primary instance, or forward paths to the current one."""
        if self._lock.tryLock(0):
            return self._start_listening()

        deadline_ms = 3000
        while deadline_ms > 0:
            socket = QLocalSocket()
            socket.connectToServer(self.server_name)
            if socket.waitForConnected(250):
                payload = json.dumps(paths, ensure_ascii=False).encode("utf-8") + b"\n"
                if socket.write(payload) != len(payload) or not socket.waitForBytesWritten(1500):
                    error = socket.errorString()
                    socket.abort()
                    raise RuntimeError(
                        f"Impossible de transmettre les fichiers à SolarSound : {error}"
                    )
                socket.disconnectFromServer()
                return False
            socket.abort()
            deadline_ms -= 250

            if self._lock.tryLock(0):
                QLocalServer.removeServer(self.server_name)
                return self._start_listening()

        raise RuntimeError(
            "Une autre instance de SolarSound détient le verrou, mais son relais "
            "de fichiers ne répond pas."
        )

    def close(self):
        self._server.close()
        if self._lock.isLocked():
            QLocalServer.removeServer(self.server_name)
            self._lock.unlock()

    def _start_listening(self) -> bool:
        if self._server.listen(self.server_name):
            return True
        QLocalServer.removeServer(self.server_name)
        if self._server.listen(self.server_name):
            return True
        error = self._server.errorString()
        self._lock.unlock()
        raise RuntimeError(f"Impossible de démarrer le relais de fichiers SolarSound : {error}")

    def _accept_connections(self):
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            self._buffers[socket] = bytearray()
            socket.readyRead.connect(lambda socket=socket: self._read_request(socket))
            socket.disconnected.connect(lambda socket=socket: self._forget_socket(socket))
            self._read_request(socket)

    def _read_request(self, socket: QLocalSocket):
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll()))
        while b"\n" in buffer:
            payload, _, remainder = buffer.partition(b"\n")
            buffer[:] = remainder
            try:
                paths = json.loads(payload.decode("utf-8"))
                if not isinstance(paths, list) or not all(
                    isinstance(path, str) for path in paths
                ):
                    raise ValueError("La requête ne contient pas une liste de chemins.")
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self.request_error.emit(f"Requête d'ouverture invalide : {exc}")
                continue
            self.queue_paths(paths)

    def _emit_pending_paths(self):
        paths = self._pending_paths
        self._pending_paths = []
        unique_paths = []
        seen_paths = set()
        for path in paths:
            normalized = os.path.normcase(os.path.abspath(path))
            if normalized not in seen_paths:
                seen_paths.add(normalized)
                unique_paths.append(path)
        if unique_paths:
            self.files_received.emit(unique_paths)

    def _forget_socket(self, socket: QLocalSocket):
        buffer = self._buffers.pop(socket, None)
        if buffer:
            self.request_error.emit("La requête d'ouverture a été interrompue.")
        socket.deleteLater()
