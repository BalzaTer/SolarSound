"""Ecran de lancement anime de SolarSound."""

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, pyqtProperty, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class _LogoWidget(QWidget):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._scale = 1.0
        self.setFixedSize(300, 300)

    def get_scale(self):
        return self._scale

    def set_scale(self, value):
        self._scale = value
        self.update()

    scale = pyqtProperty(float, get_scale, set_scale)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        size = int(150 * self._scale)
        pixmap = self._pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - pixmap.width()) // 2
        y = (self.height() - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)


class SplashScreen(QWidget):
    """Splash sans bordure avec animation du logo et progression de demarrage."""

    def __init__(self, logo_path: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(430, 390)

        logo = QPixmap(logo_path)
        if logo.isNull():
            logo = QPixmap(132, 132)
            logo.fill(QColor("#f5a623"))
        self._logo = _LogoWidget(logo, self)

        title = QLabel("SOLARSOUND")
        title.setObjectName("splash_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("LECTEUR AUDIO & VIDEO 5.1")
        subtitle.setObjectName("splash_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._status = QLabel("Preparation du lancement...")
        self._status.setObjectName("splash_status")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(7)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 34)
        layout.setSpacing(4)
        layout.addWidget(self._logo, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(22)
        layout.addWidget(self._status)
        layout.addSpacing(7)
        layout.addWidget(self._progress)

        self.setStyleSheet(
            """
            SplashScreen {
                background-color: #14110c;
                border: 1px solid #5a3d16;
                border-radius: 14px;
            }
            QLabel#splash_title {
                color: #f5a623;
                font-size: 25px;
                font-weight: bold;
                letter-spacing: 4px;
            }
            QLabel#splash_subtitle {
                color: #9a8250;
                font-size: 10px;
                letter-spacing: 2px;
            }
            QLabel#splash_status {
                color: #d6bd83;
                font-size: 11px;
            }
            QProgressBar {
                background-color: #2a2112;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #f5a623;
                border-radius: 3px;
            }
            """
        )

        self._animation = QPropertyAnimation(self._logo, b"scale", self)
        self._animation.setStartValue(0.94)
        self._animation.setKeyValueAt(0.5, 1.0)
        self._animation.setEndValue(0.96)
        self._animation.setDuration(1700)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.setLoopCount(-1)
        self._animation.start()

    def center_on_screen(self, screen=None):
        screen = screen or self.screen()
        if screen is None:
            return
        self.move(screen.availableGeometry().center() - self.rect().center())

    def set_progress(self, value: int, status: str):
        self._progress.setValue(value)
        self._status.setText(status)

    def finish(self, window):
        self._animation.stop()
        self.close()
        window.show()
        window.raise_()
        window.activateWindow()
