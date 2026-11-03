import os
import tempfile
import unittest
import wave
from unittest.mock import patch

import numpy as np
import soundfile as sf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from audio.bpm_tagging import (
    estimate_bpm,
    find_audio_files,
    process_bpm_files,
    read_bpm_tag,
    write_bpm_tag,
)
from core.playlist_manager import PlaylistManager
from ui.playlist_manager_panel import PlaylistManagerPanel
from ui.settings_panel import LibraryTab


class BpmTaggingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create_wav(self, path):
        with wave.open(path, "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(22050)
            audio_file.writeframes(b"\x00\x00" * 22050)

    def test_wav_bpm_tag_can_be_written_and_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "track.wav")
            self._create_wav(path)

            write_bpm_tag(path, 123.4)

            self.assertEqual(read_bpm_tag(path), 123.4)

    def test_flac_bpm_tag_can_be_written_and_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "track.flac")
            sf.write(path, np.zeros(22050, dtype=np.float32), 22050)

            write_bpm_tag(path, 128)

            self.assertEqual(read_bpm_tag(path), 128.0)

    def test_librosa_estimates_tempo_from_audio(self):
        sample_rate = 22050
        duration = 20
        signal = np.zeros(sample_rate * duration, dtype=np.float32)
        for beat_time in np.arange(0.25, duration, 0.5):
            start = int(beat_time * sample_rate)
            width = min(600, len(signal) - start)
            signal[start:start + width] = np.hanning(width)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "tempo.wav")
            sf.write(path, signal, sample_rate)

            bpm = estimate_bpm(path)

        self.assertGreaterEqual(bpm, 100)
        self.assertLessEqual(bpm, 130)

    def test_cancel_restores_original_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "track.mp3")
            with open(path, "wb") as audio_file:
                audio_file.write(b"original")
            stop_requested = False

            def stop_after_write(*_args):
                nonlocal stop_requested
                stop_requested = True

            def fake_write(target, bpm):
                with open(target, "wb") as audio_file:
                    audio_file.write(f"bpm={bpm}".encode("ascii"))

            with (
                patch("audio.bpm_tagging.read_bpm_tag", return_value=None),
                patch("audio.bpm_tagging.estimate_bpm", return_value=120.0),
                patch("audio.bpm_tagging.write_bpm_tag", side_effect=fake_write),
            ):
                result = process_bpm_files(
                    [path],
                    replace_existing=False,
                    report=stop_after_write,
                    should_stop=lambda: stop_requested,
                    rollback_on_stop=lambda: True,
                )

            with open(path, "rb") as audio_file:
                restored = audio_file.read()

        self.assertEqual(restored, b"original")
        self.assertTrue(result["rolled_back"])
        self.assertEqual(result["restored"], 1)
        self.assertEqual(result["written"], {})

    def test_close_stops_but_keeps_completed_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "track.mp3")
            with open(path, "wb") as audio_file:
                audio_file.write(b"original")
            stop_requested = False

            def stop_after_write(*_args):
                nonlocal stop_requested
                stop_requested = True

            def fake_write(target, bpm):
                with open(target, "wb") as audio_file:
                    audio_file.write(f"bpm={bpm}".encode("ascii"))

            with (
                patch("audio.bpm_tagging.read_bpm_tag", return_value=None),
                patch("audio.bpm_tagging.estimate_bpm", return_value=120.0),
                patch("audio.bpm_tagging.write_bpm_tag", side_effect=fake_write),
            ):
                result = process_bpm_files(
                    [path],
                    replace_existing=False,
                    report=stop_after_write,
                    should_stop=lambda: stop_requested,
                    rollback_on_stop=lambda: False,
                )

            with open(path, "rb") as audio_file:
                kept = audio_file.read()

        self.assertEqual(kept, b"bpm=120.0")
        self.assertTrue(result["stopped"])
        self.assertFalse(result["rolled_back"])
        self.assertEqual(result["written"], {path: 120.0})

    def test_existing_bpm_is_skipped_when_only_filling_empty_tags(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "track.mp3")
            with open(path, "wb") as audio_file:
                audio_file.write(b"original")

            with (
                patch("audio.bpm_tagging.read_bpm_tag", return_value=98.0),
                patch("audio.bpm_tagging.estimate_bpm") as estimate,
                patch("audio.bpm_tagging.write_bpm_tag") as write,
            ):
                result = process_bpm_files([path], replace_existing=False)

        estimate.assert_not_called()
        write.assert_not_called()
        self.assertEqual(result["skipped"], 1)

    def test_partial_tag_write_failure_restores_original_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "track.mp3")
            with open(path, "wb") as audio_file:
                audio_file.write(b"original")

            def failing_write(target, _bpm):
                with open(target, "wb") as audio_file:
                    audio_file.write(b"partial")
                raise OSError("tag write failed")

            with (
                patch("audio.bpm_tagging.read_bpm_tag", return_value=None),
                patch("audio.bpm_tagging.estimate_bpm", return_value=120.0),
                patch(
                    "audio.bpm_tagging.write_bpm_tag",
                    side_effect=failing_write,
                ),
            ):
                result = process_bpm_files([path], replace_existing=False)

            with open(path, "rb") as audio_file:
                restored = audio_file.read()

        self.assertEqual(restored, b"original")
        self.assertEqual(result["written"], {})
        self.assertEqual(len(result["errors"]), 1)

    def test_library_discovery_scans_subfolders_and_deduplicates_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dir = os.path.join(temp_dir, "nested")
            os.makedirs(nested_dir)
            audio_path = os.path.join(nested_dir, "track.wav")
            with open(audio_path, "wb") as audio_file:
                audio_file.write(b"audio")

            paths, errors, stopped = find_audio_files(
                [temp_dir, nested_dir],
                {".wav"},
            )

        self.assertEqual(paths, [audio_path])
        self.assertEqual(errors, [])
        self.assertFalse(stopped)

    def test_playlist_actions_cover_selection_and_entire_collection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PlaylistManager(app_data_dir=temp_dir)
            folder = manager.create_folder("Collection")
            playlist = manager.create_playlist("Playlist", folder_id=folder.id)
            panel = PlaylistManagerPanel(manager)
            selected = []
            all_requested = []
            panel.bpm_analysis_requested.connect(
                lambda scope, item_id: selected.append((scope, item_id))
            )
            panel.bpm_analysis_all_requested.connect(
                lambda: all_requested.append(True)
            )

            panel._current_playlist_id = playlist.id
            panel._on_analyze_bpm_selected()
            panel._current_playlist_id = None
            panel._current_folder_id = folder.id
            panel._on_analyze_bpm_selected()
            panel.btn_analyze_bpm_all.click()

            panel.close()

        self.assertEqual(
            selected,
            [("playlist", playlist.id), ("folder", folder.id)],
        )
        self.assertEqual(all_requested, [True])

    def test_library_exposes_bpm_analysis_action(self):
        tab = LibraryTab()
        requests = []
        tab.bpm_analysis_requested.connect(lambda: requests.append(True))

        tab.btn_analyze_bpm.click()
        tab.close()

        self.assertEqual(requests, [True])


if __name__ == "__main__":
    unittest.main()
