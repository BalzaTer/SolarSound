import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from audio.engine import AudioEngine
from core.session import SessionManager, SessionState
from PyQt6.QtWidgets import QApplication
from ui.settings_panel import AudioTab


class AudioNormalizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_normalizer_adjusts_playback_level_when_enabled(self):
        engine = AudioEngine()
        engine._audio_data = np.full((8, 2), 0.05, dtype=np.float32)
        engine._total_frames = len(engine._audio_data)
        engine.state = engine.STATE_PLAYING
        engine.set_normalizer(True, 100)
        output = np.zeros((8, 2), dtype=np.float32)

        engine._audio_callback(output, len(output), None, None)

        self.assertGreater(float(np.max(np.abs(output))), 0.05)
        self.assertLessEqual(float(np.max(np.abs(output))), 0.8913)

    def test_normalizer_disabled_preserves_original_level(self):
        engine = AudioEngine()
        engine._audio_data = np.full((8, 2), 0.05, dtype=np.float32)
        engine._total_frames = len(engine._audio_data)
        engine.state = engine.STATE_PLAYING
        engine.set_normalizer(False, 100)
        output = np.zeros((8, 2), dtype=np.float32)

        engine._audio_callback(output, len(output), None, None)

        np.testing.assert_allclose(output[:, 0], 0.05)

    def test_normalizer_limits_peaks_and_zero_strength_is_identity(self):
        engine = AudioEngine()
        audio_data = np.full((1000, 2), 0.001, dtype=np.float32)
        audio_data[0, 0] = 0.99
        engine._audio_data = audio_data

        engine.set_normalizer(True, 100)
        gain = engine._normalization_gain
        self.assertLessEqual(float(np.max(np.abs(audio_data))) * gain, 0.8913)

        engine.set_normalizer(True, 0)
        self.assertEqual(engine._normalization_gain, 1.0)

    def test_changing_strength_reuses_cached_track_measurements(self):
        engine = AudioEngine()
        engine._audio_data = np.full((1000, 2), 0.05, dtype=np.float32)
        with patch.object(
            engine,
            "_measure_normalization_level",
            wraps=engine._measure_normalization_level,
        ) as measure_level:
            engine.set_normalizer(True, 30)
            engine.set_normalizer(True, 60)
            engine.set_normalizer(True, 90)

        measure_level.assert_called_once()

    def test_normalizer_settings_are_persisted_in_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SessionManager()
            manager._path = os.path.join(temp_dir, "session.json")
            state = SessionState(
                normalizer_config={"enabled": True, "strength": 70}
            )

            manager.save(state)
            restored = manager.load()

        self.assertEqual(
            restored.normalizer_config,
            {"enabled": True, "strength": 70},
        )

    def test_audio_settings_emit_enabled_state_and_strength(self):
        tab = AudioTab(
            [],
            normalizer_config={"enabled": True, "strength": 40},
        )
        emitted = []
        tab.normalizer_changed.connect(emitted.append)

        tab.chk_normalizer.setChecked(False)
        self.assertFalse(tab.sld_normalizer_strength.isEnabled())
        tab.chk_normalizer.setChecked(True)
        tab.sld_normalizer_strength.setValue(80)

        self.assertEqual(
            emitted[-1],
            {"enabled": True, "strength": 80},
        )
        tab.close()


if __name__ == "__main__":
    unittest.main()
