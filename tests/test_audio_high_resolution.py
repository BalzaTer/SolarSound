import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

from audio.engine import AudioEngine


class HighResolutionPlaybackTests(unittest.TestCase):
    def test_engine_preserves_pcm24_samples_during_decode(self):
        sample_rate = 44100
        audio = np.tile(
            np.array([[0.123456, -0.654321]], dtype=np.float32),
            (128, 1),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "high-resolution.wav"
            sf.write(path, audio, sample_rate, subtype="PCM_24")
            expected, _ = sf.read(path, dtype="float32", always_2d=True)
            for soundfile_enabled in (True, False):
                engine = AudioEngine()
                with patch(
                    "audio.engine.SOUNDFILE_OK", soundfile_enabled
                ):
                    self.assertTrue(engine.load(str(path)))

                np.testing.assert_allclose(
                    engine._audio_data, expected, rtol=0, atol=1 / 8388608
                )
                quantized_16_bit = (
                    (expected * 32767).clip(-32768, 32767).astype(np.int16)
                    .astype(np.float32)
                    / 32768.0
                )
                self.assertGreater(
                    float(np.max(np.abs(engine._audio_data - quantized_16_bit))),
                    1e-5,
                )


if __name__ == "__main__":
    unittest.main()
