import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.custom_playlist import CustomTrack
from core.playlist import Playlist, Track
from ui.main_window import MainWindow


class _ListWidget:
    def __init__(self):
        self.updates_enabled = True

    def clear(self):
        pass

    def setUpdatesEnabled(self, enabled):
        self.updates_enabled = enabled


class _PlaylistWidget:
    def __init__(self):
        self.list_widget = _ListWidget()
        self.playlist_changed = SimpleNamespace(emit=lambda: None)
        self.added_tracks = []

    def _add_list_item(self, track):
        self.added_tracks.append(track)

    def _update_count(self):
        pass


class CustomFolderLoadingTests(unittest.TestCase):
    def setUp(self):
        self.window = SimpleNamespace(
            playlist=Playlist(),
            playlist_widget=_PlaylistWidget(),
            status_bar=SimpleNamespace(showMessage=Mock()),
            _load_and_play=Mock(),
        )

    def test_loads_existing_tracks_as_a_batch_and_skips_missing_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            available_path = Path(temp_dir) / "available.mp3"
            available_path.touch()
            tracks = [
                CustomTrack(path=str(available_path)),
                CustomTrack(path=str(Path(temp_dir) / "missing.mp3")),
            ]

            loaded = MainWindow._load_custom_tracks_into_playlist(
                self.window, tracks, mode="replace"
            )

        self.assertEqual(loaded, 1)
        self.assertEqual(self.window.playlist.tracks, tracks[:1])
        self.assertEqual(self.window.playlist_widget.added_tracks, tracks[:1])
        self.assertTrue(self.window.playlist_widget.list_widget.updates_enabled)
        self.window._load_and_play.assert_called_once()
        self.window.status_bar.showMessage.assert_called_once_with(
            "1 piste(s) indisponible(s) ignorée(s)", 8000
        )

    def test_does_not_clear_current_playlist_when_all_imported_files_are_missing(self):
        current_track = Track(path="current.mp3")
        self.window.playlist.add_track(current_track)

        loaded = MainWindow._load_custom_tracks_into_playlist(
            self.window,
            [CustomTrack(path="missing.mp3")],
            mode="replace",
        )

        self.assertEqual(loaded, 0)
        self.assertEqual(self.window.playlist.tracks, [current_track])
        self.window._load_and_play.assert_not_called()
        self.window.status_bar.showMessage.assert_called_once_with(
            "Aucune piste disponible (1 ignorée(s))", 8000
        )


if __name__ == "__main__":
    unittest.main()
