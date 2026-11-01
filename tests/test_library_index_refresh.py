import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.settings_panel import LibraryTab


class LibraryIndexRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_refresh_button_uses_rotation_icon_and_emits_request(self):
        tab = LibraryTab()
        requests = []
        tab.refresh_requested.connect(lambda: requests.append(True))

        self.assertFalse(tab.btn_refresh.icon().isNull())
        tab.btn_refresh.click()

        self.assertEqual(requests, [True])
        tab.close()

    def test_controls_are_disabled_during_indexing(self):
        tab = LibraryTab()

        tab.set_indexing(True)

        self.assertFalse(tab.btn_refresh.isEnabled())
        self.assertFalse(tab.btn_add.isEnabled())
        self.assertFalse(tab.btn_remove.isEnabled())
        self.assertFalse(tab.list_folders.isEnabled())

        tab.set_indexing(False)

        self.assertTrue(tab.btn_refresh.isEnabled())
        self.assertTrue(tab.btn_add.isEnabled())
        tab.close()


if __name__ == "__main__":
    unittest.main()
