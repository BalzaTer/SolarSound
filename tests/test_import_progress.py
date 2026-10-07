import unittest
from unittest.mock import patch

from core.playlist import Track
from ui.playlist_widget import PlaylistMetadataWorker


class PlaylistMetadataProgressTests(unittest.TestCase):
    def test_worker_reports_progress_for_successful_and_failed_metadata_reads(self):
        tracks = [Track(path="first.mp3"), Track(path="second.mp3")]
        worker = PlaylistMetadataWorker(tracks)
        progress = []
        results = []
        worker.progress.connect(lambda current, total, path: progress.append(
            (current, total, path)
        ))
        worker.result_ready.connect(results.append)

        with patch(
            "ui.playlist_widget.read_metadata",
            side_effect=[RuntimeError("invalid tags"), {"title": "Second"}],
        ):
            worker.run()

        self.assertEqual(progress, [
            (1, 2, "first.mp3"),
            (2, 2, "second.mp3"),
        ])
        self.assertEqual(results, [[(tracks[1], {"title": "Second"})]])


if __name__ == "__main__":
    unittest.main()
