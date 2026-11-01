import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from core.session import (
    MAX_POSITION_SAVE_INTERVAL_SECONDS,
    MIN_POSITION_SAVE_INTERVAL_SECONDS,
    POSITION_SAVE_INTERVAL_SECONDS,
    SessionManager,
    SessionState,
    normalize_position_save_interval,
)
from ui.settings_panel import StartupTab
from ui.main_window import MainWindow


class ResumePositionSettingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_startup_tab_emits_resume_position_choice(self):
        tab = StartupTab({"resume_position": False})
        self.assertFalse(tab.cmb_resume_position.currentData())
        choices = []
        tab.resume_position_changed.connect(choices.append)

        resume_index = tab.cmb_resume_position.findData(True)
        tab.cmb_resume_position.setCurrentIndex(resume_index)

        self.assertEqual(choices, [True])
        tab._emit_changed()
        self.assertTrue(tab._config["resume_position"])
        tab.close()

    def test_startup_tab_exposes_interval_from_one_to_thirty_seconds(self):
        tab = StartupTab()
        intervals = []
        tab.position_save_interval_changed.connect(intervals.append)

        self.assertEqual(tab.spn_position_save_interval.minimum(), 1)
        self.assertEqual(tab.spn_position_save_interval.maximum(), 30)
        self.assertEqual(tab.spn_position_save_interval.value(), 10)

        tab.spn_position_save_interval.setValue(1)
        tab.spn_position_save_interval.setValue(30)

        self.assertEqual(intervals, [1, 30])
        self.assertEqual(tab._config["position_save_interval_seconds"], 30)
        tab.close()

    def test_resume_position_choice_is_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SessionManager()
            manager._path = os.path.join(temp_dir, "session.json")
            manager.save(SessionState(
                player_position=127.9,
                resume_position_on_startup=False,
            ))

            restored = manager.load()
            with open(manager.path, "r", encoding="utf-8") as session_file:
                session_json = session_file.read()

        self.assertFalse(restored.resume_position_on_startup)
        self.assertEqual(restored.player_position, 0)
        self.assertEqual(
            restored.position_save_interval_seconds,
            POSITION_SAVE_INTERVAL_SECONDS,
        )
        self.assertIn('"resume_position_on_startup": false', session_json)
        self.assertNotIn('"player_position"', session_json)
        self.assertIn('"position_save_interval_seconds": 10', session_json)

    def test_position_is_saved_as_the_last_completed_ten_second_interval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SessionManager()
            manager._path = os.path.join(temp_dir, "session.json")

            manager.save(SessionState(player_position=9.9))
            before_ten_seconds = manager.load().player_position
            manager.save(SessionState(player_position=10.0))
            at_ten_seconds = manager.load().player_position
            manager.save(SessionState(player_position=19.9))
            before_twenty_seconds = manager.load().player_position

        self.assertEqual(before_ten_seconds, 0)
        self.assertEqual(at_ten_seconds, 10)
        self.assertEqual(before_twenty_seconds, 10)

    def test_custom_interval_is_persisted_and_used_to_round_position(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SessionManager()
            manager._path = os.path.join(temp_dir, "session.json")
            manager.save(SessionState(
                player_position=89.9,
                position_save_interval_seconds=30,
            ))

            restored = manager.load()

        self.assertEqual(restored.player_position, 60)
        self.assertEqual(restored.position_save_interval_seconds, 30)

    def test_resume_disabled_does_not_save_position_even_if_json_had_one(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SessionManager()
            manager._path = os.path.join(temp_dir, "session.json")
            with open(manager._path, "w", encoding="utf-8") as session_file:
                session_file.write('{"player_position": 250}')

            manager.save(SessionState(
                player_position=127.9,
                resume_position_on_startup=False,
            ))

            with open(manager.path, "r", encoding="utf-8") as session_file:
                saved_data = session_file.read()
            restored = manager.load()

        self.assertNotIn('"player_position"', saved_data)
        self.assertEqual(restored.player_position, 0.0)
        self.assertFalse(restored.resume_position_on_startup)

    def test_saved_interval_is_clamped_to_supported_range(self):
        self.assertEqual(
            normalize_position_save_interval(0),
            MIN_POSITION_SAVE_INTERVAL_SECONDS,
        )
        self.assertEqual(
            normalize_position_save_interval(99),
            MAX_POSITION_SAVE_INTERVAL_SECONDS,
        )
        self.assertEqual(
            normalize_position_save_interval("invalid"),
            POSITION_SAVE_INTERVAL_SECONDS,
        )

    def test_invalid_saved_interval_is_clamped_when_loading_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SessionManager()
            manager._path = os.path.join(temp_dir, "session.json")
            with open(manager._path, "w", encoding="utf-8") as session_file:
                session_file.write('{"position_save_interval_seconds": 99}')

            restored = manager.load()

        self.assertEqual(
            restored.position_save_interval_seconds,
            MAX_POSITION_SAVE_INTERVAL_SECONDS,
        )

    def test_position_save_timer_uses_selected_interval(self):
        timer = SimpleNamespace(start=Mock())
        window = SimpleNamespace(
            _position_save_timer=timer,
            _schedule_save=Mock(),
        )

        MainWindow._on_position_save_interval_changed(window, 30)

        self.assertEqual(window._position_save_interval_seconds, 30)
        timer.start.assert_called_once_with(30000)
        window._schedule_save.assert_called_once_with()

    def test_close_saves_before_stopping_audio_engine(self):
        events = []
        window = SimpleNamespace(
            _save_session=lambda: events.append("save"),
            _preview_player=SimpleNamespace(
                shutdown=lambda: events.append("preview shutdown")
            ),
            engine=SimpleNamespace(stop=lambda: events.append("engine stop")),
            video_engine=SimpleNamespace(
                release=lambda: events.append("video release")
            ),
        )
        event = SimpleNamespace(accept=Mock())

        MainWindow.closeEvent(window, event)

        self.assertEqual(
            events,
            ["save", "preview shutdown", "engine stop", "video release"],
        )
        event.accept.assert_called_once_with()

    def test_older_sessions_default_to_resuming_saved_position(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SessionManager()
            manager._path = os.path.join(temp_dir, "session.json")
            with open(manager._path, "w", encoding="utf-8") as session_file:
                session_file.write("{}")

            restored = manager.load()

        self.assertTrue(restored.resume_position_on_startup)


if __name__ == "__main__":
    unittest.main()
