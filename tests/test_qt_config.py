import os
import unittest

from core.qt_config import configure_qt_environment


class QtConfigTests(unittest.TestCase):
    def test_configure_qt_environment_sets_ffmpeg_logging_rule(self):
        os.environ.pop("QT_LOGGING_RULES", None)

        configure_qt_environment()

        self.assertEqual(os.environ["QT_LOGGING_RULES"], "qt.multimedia.ffmpeg=false")


if __name__ == "__main__":
    unittest.main()
