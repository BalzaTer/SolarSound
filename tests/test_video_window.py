import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget

from ui.video_window import VideoWindow


def make_video_window_state(detached, main_screen, detached_screen):
    calls = []
    main_window = SimpleNamespace(screen=lambda: main_screen)
    video_window = SimpleNamespace(
        _detached=detached,
        _fullscreen=False,
        window=lambda: main_window,
        screen=lambda: detached_screen,
        parentWidget=lambda: None,
        _find_tab_widget=lambda: None,
        _restore_tab_after_fullscreen=lambda: False,
        _fullscreen_tab_state=None,
        winId=lambda: calls.append(("winId",)),
        setGeometry=lambda geometry: calls.append(("setGeometry", geometry)),
        setWindowFlags=lambda flags: calls.append(("setWindowFlags", flags)),
        showFullScreen=lambda: calls.append(("showFullScreen",)),
        showNormal=lambda: calls.append(("showNormal",)),
        show=lambda: calls.append(("show",)),
        _show_controls_temp=lambda: calls.append(("showControls",)),
    )
    return video_window, calls


class VideoWindowFullscreenTests(unittest.TestCase):
    def test_fullscreen_takes_video_out_of_tab_layout_and_restores_it(self):
        app = QApplication.instance()
        if app is None:
            if QCoreApplication.instance() is not None:
                self.skipTest("A QCoreApplication already exists without GUI support")
            app = QApplication([])

        class Engine:
            STATE_PLAYING = 1
            STATE_PAUSED = 2
            state = 0
            position_seconds = 0.0
            duration_seconds = 0.0
            config = SimpleNamespace(speed=1.0)
            on_track_ended = None

            def create_video_widget(self):
                return QWidget()

            set_speed = Mock()
            step_forward = Mock()
            step_backward = Mock()
            seek = Mock()
            play = Mock()
            pause = Mock()
            set_subtitle_file = Mock()

        tabs = QTabWidget()
        tabs.addTab(QWidget(), "Autre")
        video = VideoWindow(Engine(), "")
        video_index = tabs.addTab(video, "Vidéo")
        tabs.setCurrentIndex(video_index)
        tabs.show()
        app.processEvents()
        target_screen = tabs.window().screen()
        screen_geometry = target_screen.geometry()

        try:
            video._toggle_fullscreen()
            loop = QEventLoop()
            QTimer.singleShot(100, loop.quit)
            loop.exec()

            self.assertTrue(video.isFullScreen())
            self.assertEqual(video.windowHandle().screen(), target_screen)
            self.assertEqual(video.geometry().size(), screen_geometry.size())
            self.assertFalse(video._detached)
            self.assertEqual(tabs.count(), 2)
            self.assertEqual(tabs.tabText(video_index), "Vidéo")

            video._toggle_fullscreen()
            app.processEvents()

            self.assertFalse(video.isFullScreen())
            self.assertEqual(tabs.indexOf(video), video_index)
            self.assertEqual(tabs.currentWidget(), video)
            self.assertEqual(tabs.count(), 2)

            video._toggle_fullscreen()
            loop = QEventLoop()
            QTimer.singleShot(100, loop.quit)
            loop.exec()
            video.detach()
            self.assertTrue(video._detached)
            self.assertTrue(video.isFullScreen())

            video._toggle_fullscreen()
            app.processEvents()
            self.assertFalse(video.isFullScreen())
            self.assertEqual(tabs.indexOf(video), -1)
            self.assertEqual(tabs.count(), 2)

            video.reattach()
            self.assertFalse(video._detached)
            self.assertEqual(tabs.indexOf(video), video_index)
            self.assertEqual(tabs.count(), 2)
        finally:
            if video._fullscreen:
                video._toggle_fullscreen()
            if video._detached:
                video.reattach()
            video._ui_timer.stop()
            video._hide_timer.stop()
            tabs.close()
            video.close()
            tabs.deleteLater()
            app.processEvents()

    def test_fullscreen_uses_main_window_screen_without_detaching(self):
        main_geometry = object()
        main_screen = SimpleNamespace(geometry=lambda: main_geometry)
        detached_screen = object()
        video_window, calls = make_video_window_state(
            False, main_screen, detached_screen
        )

        VideoWindow._toggle_fullscreen(video_window)

        self.assertTrue(video_window._fullscreen)
        self.assertFalse(video_window._detached)
        self.assertIn(("setWindowFlags", Qt.WindowType.Window), calls)
        self.assertLess(
            calls.index(("setGeometry", main_geometry)),
            calls.index(("show",)),
        )
        self.assertLess(
            calls.index(("show",)),
            calls.index(("showFullScreen",)),
        )
        self.assertIn(("showFullScreen",), calls)

        VideoWindow._toggle_fullscreen(video_window)

        self.assertFalse(video_window._fullscreen)
        self.assertFalse(video_window._detached)
        self.assertIn(("setWindowFlags", Qt.WindowType.Widget), calls)
        self.assertIn(("showNormal",), calls)

    def test_fullscreen_uses_detached_window_screen(self):
        main_screen = object()
        detached_screen = object()
        video_window, calls = make_video_window_state(
            True, main_screen, detached_screen
        )

        VideoWindow._toggle_fullscreen(video_window)

        self.assertTrue(video_window._fullscreen)
        self.assertTrue(video_window._detached)
        self.assertNotIn(("setWindowFlags", Qt.WindowType.Window), calls)
        self.assertFalse(any(call[0] == "setGeometry" for call in calls))
        self.assertIn(("showFullScreen",), calls)

    def test_detach_actions_preserve_fullscreen_state(self):
        button = SimpleNamespace(
            setToolTip=Mock(),
            setText=Mock(),
        )
        video_window = SimpleNamespace(
            _detached=False,
            _fullscreen=True,
            controls=SimpleNamespace(btn_detach=button),
            setWindowTitle=Mock(),
        )

        VideoWindow.detach(video_window)
        self.assertTrue(video_window._detached)
        self.assertTrue(video_window._fullscreen)

        VideoWindow.reattach(video_window)
        self.assertFalse(video_window._detached)
        self.assertTrue(video_window._fullscreen)


if __name__ == "__main__":
    unittest.main()
