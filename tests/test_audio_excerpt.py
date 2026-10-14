import unittest
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from audio.engine import decode_audio_excerpt, decode_audio_file


class AudioExcerptTests(unittest.TestCase):
    def test_excerpt_decoder_reads_center_segment(self):
        sample_rate = 8000
        audio = np.column_stack((
            np.linspace(-0.8, 0.8, sample_rate * 10, dtype=np.float32),
            np.linspace(0.8, -0.8, sample_rate * 10, dtype=np.float32),
        ))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "long.wav"
            sf.write(path, audio, sample_rate)
            excerpt, returned_rate = decode_audio_excerpt(str(path), 2.0)
            decoded, _ = decode_audio_file(str(path))

        self.assertEqual(returned_rate, sample_rate)
        self.assertEqual(excerpt.shape, (sample_rate * 2, 2))
        start = len(decoded) // 2 - sample_rate
        np.testing.assert_array_equal(excerpt, decoded[start:start + sample_rate * 2])


if __name__ == "__main__":
    unittest.main()
