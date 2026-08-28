"""Barre de progression audio avec aperçu de l'intensite par segments."""

import numpy as np
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QSlider, QWidget


class ClickableProgressSlider(QSlider):
    """Curseur dont la position suit la souris pendant le clic gauche."""

    def _value_from_x(self, x: float) -> int:
        width = max(1, self.width())
        ratio = max(0.0, min(1.0, x / width))
        return round(self.minimum() + ratio * (self.maximum() - self.minimum()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setSliderPosition(self._value_from_x(event.position().x()))
            self.setSliderDown(True)
            self.sliderPressed.emit()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown() and event.buttons() & Qt.MouseButton.LeftButton:
            self.setSliderPosition(self._value_from_x(event.position().x()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setSliderPosition(self._value_from_x(event.position().x()))
            self.setSliderDown(False)
            self.sliderReleased.emit()
            return
        super().mouseReleaseEvent(event)


class IntensityProgressBar(QWidget):
    position_requested = pyqtSignal(int)
    position_released = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._levels = np.zeros(80, dtype=np.float32)
        self._progress = 0
        self._accent = QColor("#f5a623")
        self._background = QColor("#2a2416")
        self._centered = False
        self.setMinimumHeight(30)
        self.setMaximumHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_levels(self, levels):
        values = np.asarray(levels, dtype=np.float32)
        self._levels = np.clip(values, 0.08, 1.0) if values.size else np.zeros(80, dtype=np.float32)
        self.update()

    def set_progress(self, value: int):
        self._progress = max(0, min(1000, int(value)))
        self.update()

    def set_theme_colors(self, colors: dict):
        self._accent = QColor(colors.get("accent", "#f5a623"))
        self._background = QColor(colors.get("border", "#2a2416"))
        self.update()

    def set_variant(self, centered: bool):
        self._centered = centered
        self.setMinimumHeight(42 if centered else 30)
        self.setMaximumHeight(56 if centered else 42)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._emit_position(event.position().x())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._emit_position(event.position().x())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.position_released.emit()
        super().mouseReleaseEvent(event)

    def _emit_position(self, x: float):
        value = round(x / max(1, self.width()) * 1000)
        self.position_requested.emit(max(0, min(1000, value)))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        count = len(self._levels)
        if width <= 0 or height <= 0 or count == 0:
            return
        gap = 2 if self._centered else 2
        bar_width = max(1.0, (width - gap * (count - 1)) / count)
        played_until = self._progress / 1000 * width
        for index, level in enumerate(self._levels):
            x = index * (bar_width + gap)
            bar_height = max(2.0, float(level) * (height - 4))
            y = (height - bar_height) / 2 if self._centered else height - bar_height
            color = QColor(self._accent if x + bar_width / 2 <= played_until else self._background)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            capsule_width = max(1.0, bar_width)
            painter.drawRoundedRect(
                QRectF(x, y, capsule_width, bar_height),
                capsule_width / 2, capsule_width / 2,
                Qt.SizeMode.AbsoluteSize
            )
