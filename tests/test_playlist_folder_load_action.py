import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from core.custom_playlist import CustomTrack
from core.playlist_manager import PlaylistManager
from ui.playlist_manager_panel import PlaylistManagerPanel


class PlaylistFolderLoadActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            if QCoreApplication.instance() is not None:
                raise RuntimeError("A QApplication is required for this test")
            cls.app = QApplication([])

    def test_folder_actions_emit_string_scopes_without_crashing(self):
        with tempfile.TemporaryDirectory() as app_data_dir:
            manager = PlaylistManager(app_data_dir=app_data_dir)
            folder = manager.create_folder("Test")
            playlist = manager.create_playlist("Playlist", folder_id=folder.id)
            playlist.tracks.append(CustomTrack(path="track.mp3"))

            panel = PlaylistManagerPanel(manager)
            self.addCleanup(panel.close)
            panel._current_folder_id = folder.id
            emitted = []
            panel.load_folder_requested.connect(
                lambda folder_id, scope: emitted.append((folder_id, scope))
            )

            panel.act_load_folder.trigger()
            panel.act_load_folder_recursive.trigger()

            self.assertEqual(
                emitted,
                [(folder.id, "folder"), (folder.id, "recursive")],
            )


if __name__ == "__main__":
    unittest.main()
