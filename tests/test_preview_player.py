import unittest
import threading
from unittest.mock import patch

import numpy as np
from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer

from audio import preview_player


class PreviewPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_preview_decodes_and_starts_playback_asynchronously(self):
        player = preview_player.PreviewPlayer()
        started = []
        loop = QEventLoop()
        player.excerpt_started.connect(
            lambda duration: (started.append(duration), loop.quit())
        )
        decode_started = threading.Event()
        finish_decode = threading.Event()

        def decode_excerpt(*_args):
            decode_started.set()
            finish_decode.wait(timeout=3)
            return np.zeros((6000, 2), dtype=np.int16), 1000

        with (
            patch.object(preview_player, "SOUNDDEVICE_OK", True),
            patch.object(preview_player, "decode_audio_excerpt") as decode,
            patch.object(preview_player.sd, "play") as play,
            patch.object(preview_player.sd, "stop"),
        ):
            decode.side_effect = decode_excerpt
            try:
                player.play_excerpt("song.mp3")
                self.assertTrue(decode_started.wait(timeout=2))
                self.assertEqual(started, [])
                finish_decode.set()
                QTimer.singleShot(3000, loop.quit)
                loop.exec()
                self.assertEqual(started, [6.0])
                play.assert_called_once()
            finally:
                finish_decode.set()
                player.shutdown()


if __name__ == "__main__":
    unittest.main()
