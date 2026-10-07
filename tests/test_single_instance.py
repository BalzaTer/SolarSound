import time
import os
import tempfile
import threading
import unittest
import uuid

from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer

from core.single_instance import SingleInstanceServer


class SingleInstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_second_instance_forwards_all_paths_to_primary(self):
        server_name = f"SolarSound.Tests.{uuid.uuid4().hex}"
        lock_path = os.path.join(tempfile.gettempdir(), f"{server_name}.lock")
        primary = SingleInstanceServer(server_name, lock_path)
        secondary = SingleInstanceServer(server_name, lock_path)
        received = []
        primary.files_received.connect(received.append)
        forwarding_result = []
        forwarding_error = []

        try:
            self.assertTrue(primary.listen_or_forward([]))
            paths = ["C:\\Music\\été\\track #1.mp3", "C:\\Music\\line\nbreak.mp4"]
            forwarding_thread = threading.Thread(
                target=lambda: self._forward(
                    secondary, paths, forwarding_result, forwarding_error
                )
            )
            forwarding_thread.start()

            deadline = time.monotonic() + 2
            while (
                (forwarding_thread.is_alive() or not received)
                and time.monotonic() < deadline
            ):
                self.app.processEvents()
                time.sleep(0.01)
            forwarding_thread.join(timeout=0.1)

            self.assertFalse(forwarding_thread.is_alive())
            self.assertEqual(forwarding_error, [])
            self.assertEqual(forwarding_result, [False])
            self.assertEqual(received, [paths])

            secondary.close()
            secondary = SingleInstanceServer(server_name, lock_path)
            next_paths = ["C:\\Music\\next.flac", "C:\\Music\\NEXT.FLAC"]
            forwarding_results = []
            forwarding_errors = []
            forwarding_threads = []

            def start_forward(file_path):
                thread = threading.Thread(
                    target=lambda: self._forward(
                        secondary,
                        [file_path],
                        forwarding_results,
                        forwarding_errors,
                    )
                )
                forwarding_threads.append(thread)
                thread.start()

            start_forward(next_paths[0])
            QTimer.singleShot(300, lambda: start_forward(next_paths[1]))

            loop = QEventLoop()
            QTimer.singleShot(3500, loop.quit)
            primary.files_received.connect(
                lambda _: loop.quit() if len(received) >= 2 else None
            )
            loop.exec()
            for thread in forwarding_threads:
                thread.join(timeout=0.1)

            self.assertTrue(all(not thread.is_alive() for thread in forwarding_threads))
            self.assertEqual(forwarding_errors, [])
            self.assertEqual(forwarding_results, [False, False])
            self.assertEqual(received[0], paths)
            self.assertEqual(len(received), 2)
            self.assertEqual(len(received[1]), 1)
            self.assertEqual(received[1][0].casefold(), next_paths[0].casefold())
        finally:
            secondary.close()
            primary.close()

    @staticmethod
    def _forward(server, paths, result, errors):
        try:
            result.append(server.listen_or_forward(paths))
        except RuntimeError as exc:
            errors.append(exc)


if __name__ == "__main__":
    unittest.main()
