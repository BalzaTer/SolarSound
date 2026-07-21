import json
import os
import tempfile
import unittest

from core.error_logging import append_error_log, collect_file_characteristics


class ErrorLoggingTests(unittest.TestCase):
    def test_append_error_log_writes_file_characteristics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "playback_errors.log")
            file_path = os.path.join(tmpdir, "bad_song.mp3")
            with open(file_path, "wb") as fh:
                fh.write(b"abc")

            append_error_log(
                message="Impossible de lire le fichier",
                file_path=file_path,
                log_path=log_path,
                context={"kind": "audio"},
            )

            with open(log_path, "r", encoding="utf-8") as fh:
                entry = json.loads(fh.read().strip())

            self.assertEqual(entry["message"], "Impossible de lire le fichier")
            self.assertEqual(entry["file_path"], file_path)
            self.assertEqual(entry["kind"], "audio")
            self.assertEqual(entry["extension"], ".mp3")
            self.assertEqual(entry["size_bytes"], 3)


if __name__ == "__main__":
    unittest.main()
