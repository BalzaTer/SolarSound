import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from audio.engine import AudioEngine
from ui.main_window import MainWindow


class AudioEngineResumePositionTests(unittest.TestCase):
    def make_engine(self):
        engine = AudioEngine()
        engine._audio_data = np.zeros((100, 2), dtype=np.float32)
        engine._sample_rate = 1
        engine._total_frames = len(engine._audio_data)
        engine._simulation_mode = True
        engine._start_simulation = Mock()
        return engine

    def test_play_preserves_a_position_restored_before_first_play(self):
        engine = self.make_engine()
        engine.seek(30)

        engine.play()

        self.assertEqual(engine.position_seconds, 30)
        engine._start_simulation.assert_called_once_with()

    def test_play_starts_from_beginning_after_explicit_stop(self):
        engine = self.make_engine()
        engine.seek(30)
        engine.stop()

        engine.play()

        self.assertEqual(engine.position_seconds, 0)

    def test_play_restarts_from_beginning_after_track_reaches_end(self):
        engine = self.make_engine()
        engine._position = engine._total_frames

        engine.play()

        self.assertEqual(engine.position_seconds, 0)

    def test_play_button_resumes_loaded_track_without_reloading_it(self):
        track = SimpleNamespace(path="track.mp3", title="Track")
        engine = SimpleNamespace(
            state=AudioEngine.STATE_STOPPED,
            has_loaded_audio=True,
            play=Mock(),
        )
        window = SimpleNamespace(
            _media_mode="audio",
            engine=engine,
            playlist=SimpleNamespace(
                tracks=[track],
                current_index=0,
                current_track=track,
                play_mode=None,
            ),
            _current_media_path=track.path,
            _set_play_icon=Mock(),
            status_bar=SimpleNamespace(showMessage=Mock()),
            _load_and_play=Mock(),
        )

        MainWindow._on_play_pause(window)

        engine.play.assert_called_once_with()
        window._load_and_play.assert_not_called()
        window._set_play_icon.assert_called_once_with(True)

    def test_play_button_loads_a_different_selected_track(self):
        track = SimpleNamespace(path="next.mp3", title="Next")
        engine = SimpleNamespace(
            state=AudioEngine.STATE_STOPPED,
            has_loaded_audio=True,
            play=Mock(),
        )
        window = SimpleNamespace(
            _media_mode="audio",
            engine=engine,
            playlist=SimpleNamespace(
                tracks=[track],
                current_index=0,
                current_track=track,
                play_mode=None,
            ),
            _current_media_path="previous.mp3",
            _set_play_icon=Mock(),
            status_bar=SimpleNamespace(showMessage=Mock()),
            _load_and_play=Mock(),
        )

        MainWindow._on_play_pause(window)

        window._load_and_play.assert_called_once_with(track, 0)
        engine.play.assert_not_called()


if __name__ == "__main__":
    unittest.main()
