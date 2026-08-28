"""Egaliseur graphique et multi-bandes de SolarSound."""

import math
from copy import deepcopy

from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel,
    QSlider, QStackedWidget, QGroupBox, QInputDialog, QMessageBox,
)


DEFAULT_FREQUENCIES = [20, 80, 200, 500, 1250, 3000, 7500, 16000]
DEFAULT_GAINS = [0.0] * len(DEFAULT_FREQUENCIES)
DEFAULT_PRESETS = {
    "Plat": DEFAULT_GAINS,
    "Bass boost": [5.0, 6.0, 4.0, 2.0, 0.0, 0.0, 0.0, 0.0],
    "Vocal": [-2.0, -1.0, 0.0, 2.0, 3.0, 2.0, 1.0, 0.0],
    "Rock": [4.0, 3.0, 1.0, -1.0, -2.0, 1.0, 3.0, 4.0],
}


class EqualizerSlider(QSlider):
    reset_requested = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setValue(0)
            self.reset_requested.emit()
        super().mouseDoubleClickEvent(event)


def normalise_equalizer_config(config: dict | None) -> dict:
    config = config or {}
    frequencies = config.get("frequencies", DEFAULT_FREQUENCIES)
    gains = config.get("gains", DEFAULT_GAINS)
    if not isinstance(frequencies, list) or len(frequencies) < 2:
        frequencies = list(DEFAULT_FREQUENCIES)
    if not isinstance(gains, list) or len(gains) != len(frequencies):
        gains = [0.0] * len(frequencies)
    free_frequencies = config.get("free_frequencies", frequencies)
    free_gains = config.get("free_gains", gains)
    if not isinstance(free_frequencies, list) or not isinstance(free_gains, list) or len(free_frequencies) != len(free_gains) or len(free_frequencies) < 2:
        free_frequencies, free_gains = list(frequencies), list(gains)
    presets = config.get("presets", {})
    if not isinstance(presets, dict):
        presets = {}
    merged = {name: list(values) for name, values in DEFAULT_PRESETS.items()}
    merged.update({str(name): list(values) for name, values in presets.items() if isinstance(values, list)})
    return {
        "enabled": bool(config.get("enabled", True)),
        "frequencies": [max(20, min(20000, float(value))) for value in frequencies],
        "gains": [max(-12.0, min(12.0, float(value))) for value in gains],
        "free_frequencies": [max(20, min(20000, float(value))) for value in free_frequencies],
        "free_gains": [max(-12.0, min(12.0, float(value))) for value in free_gains],
        "presets": merged,
        "current_preset": str(config.get("current_preset", "Plat")),
        "mode": config.get("mode", "bands"),
    }


class EqualizerGraph(QWidget):
    points_changed = pyqtSignal(object)

    def __init__(self, frequencies, gains, parent=None):
        super().__init__(parent)
        self.frequencies = list(frequencies)
        self.gains = list(gains)
        self._drag_index = None
        self.setMinimumHeight(280)
        self.setMouseTracking(True)
        self.setToolTip("Clic : ajouter un point | Clic droit : supprimer | Glisser : déplacer")

    def set_points(self, frequencies, gains):
        self.frequencies = list(frequencies)
        self.gains = list(gains)
        self.update()

    def set_theme_colors(self, colors: dict):
        self._theme_colors = colors
        self.update()

    def _plot_rect(self):
        return self.rect().adjusted(44, 18, -20, -34)

    def _x(self, frequency):
        rect = self._plot_rect()
        return rect.left() + (math.log10(max(20, frequency)) - math.log10(20)) / 3.0 * rect.width()

    def _y(self, gain):
        rect = self._plot_rect()
        return rect.center().y() - (gain / 12.0) * (rect.height() / 2)

    def _point_at(self, pos):
        for index, frequency in enumerate(self.frequencies):
            if (QPointF(self._x(frequency), self._y(self.gains[index])) - pos).manhattanLength() < 18:
                return index
        return None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._plot_rect()
        colors = getattr(self, "_theme_colors", {})
        painter.fillRect(self.rect(), QColor(colors.get("bg_list", "#0c0a07")))
        painter.setPen(QPen(QColor(colors.get("border_bright", "#3d3420")), 1))
        for gain in (-12, -6, 0, 6, 12):
            y = self._y(gain)
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))
            painter.drawText(5, int(y + 4), f"{gain:+d}")
        for frequency in (20, 80, 200, 500, 1250, 3000, 7500, 16000):
            x = self._x(frequency)
            painter.drawLine(int(x), rect.top(), int(x), rect.bottom())
            painter.drawText(int(x - 15), self.height() - 10, f"{frequency:g}")
        painter.setPen(QPen(QColor(colors.get("accent", "#f5a623")), 3))
        path = QPainterPath()
        for index, frequency in enumerate(self.frequencies):
            point = QPointF(self._x(frequency), self._y(self.gains[index]))
            if index == 0:
                path.moveTo(point)
            else:
                previous = QPointF(self._x(self.frequencies[index - 1]), self._y(self.gains[index - 1]))
                midpoint = (previous.x() + point.x()) / 2
                path.cubicTo(midpoint, previous.y(), midpoint, point.y(), point.x(), point.y())
        painter.drawPath(path)
        painter.setBrush(QBrush(QColor(colors.get("accent", "#f5a623"))))
        painter.setPen(QPen(QColor(colors.get("bg_main", "#0f0d0a")), 2))
        for index, frequency in enumerate(self.frequencies):
            painter.drawEllipse(QPointF(self._x(frequency), self._y(self.gains[index])), 6, 6)

    def mousePressEvent(self, event):
        index = self._point_at(event.position())
        if event.button() == Qt.MouseButton.RightButton and index is not None and len(self.frequencies) > 2:
            self.frequencies.pop(index)
            self.gains.pop(index)
            self.points_changed.emit(self._points())
            self.update()
        elif event.button() == Qt.MouseButton.LeftButton:
            if index is not None:
                self._drag_index = index
            else:
                rect = self._plot_rect()
                x = max(rect.left(), min(rect.right(), event.position().x()))
                y = max(rect.top(), min(rect.bottom(), event.position().y()))
                frequency = 20 * (1000 ** ((x - rect.left()) / rect.width()))
                gain = max(-12.0, min(12.0, (rect.center().y() - y) / (rect.height() / 2) * 12))
                self.frequencies.append(frequency)
                self.gains.append(gain)
                ordered = sorted(zip(self.frequencies, self.gains))
                self.frequencies, self.gains = map(list, zip(*ordered))
                self._drag_index = self.frequencies.index(frequency)
                self.points_changed.emit(self._points())
                self.update()

    def mouseMoveEvent(self, event):
        if self._drag_index is None:
            return
        rect = self._plot_rect()
        x = max(rect.left(), min(rect.right(), event.position().x()))
        y = max(rect.top(), min(rect.bottom(), event.position().y()))
        frequency = 20 * (1000 ** ((x - rect.left()) / rect.width()))
        gain = max(-12.0, min(12.0, (rect.center().y() - y) / (rect.height() / 2) * 12))
        if self._drag_index > 0:
            frequency = max(frequency, self.frequencies[self._drag_index - 1] + 1)
        if self._drag_index < len(self.frequencies) - 1:
            frequency = min(frequency, self.frequencies[self._drag_index + 1] - 1)
        self.frequencies[self._drag_index] = frequency
        self.gains[self._drag_index] = gain
        self.points_changed.emit(self._points())
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag_index = None

    def _points(self):
        return {"frequencies": list(self.frequencies), "gains": list(self.gains)}


class EqualizerPanel(QWidget):
    config_changed = pyqtSignal(dict)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = normalise_equalizer_config(config)
        self._sliders = []
        self._build_ui()
        self._load_points(self.config["frequencies"], self.config["gains"])
        if self.config["mode"] == "free":
            self.graph.set_points(self.config["free_frequencies"], self.config["free_gains"])

    def _build_ui(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.enabled = QPushButton("EQ actif")
        self.enabled.setCheckable(True)
        self.enabled.setChecked(self.config["enabled"])
        self.enabled.clicked.connect(self._emit)
        top.addWidget(self.enabled)
        top.addWidget(QLabel("Preset"))
        self.preset = QComboBox()
        self.preset.addItems(self.config["presets"])
        self.preset.setCurrentText(self.config["current_preset"])
        self.preset.currentTextChanged.connect(self._preset_selected)
        top.addWidget(self.preset, 1)
        save = QPushButton("Enregistrer")
        save.clicked.connect(self._save_preset)
        top.addWidget(save)
        delete = QPushButton("Supprimer")
        delete.clicked.connect(self._delete_preset)
        top.addWidget(delete)
        root.addLayout(top)

        self.mode = QComboBox()
        self.mode.addItems(["Curseurs par bandes", "Courbe libre"])
        self.mode.setCurrentIndex(1 if self.config["mode"] == "free" else 0)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        root.addWidget(self.mode)
        self.stack = QStackedWidget()
        self.slider_page = QWidget()
        slider_layout = QHBoxLayout(self.slider_page)
        slider_layout.setSpacing(8)
        self._slider_layout = slider_layout
        self.graph = EqualizerGraph([], [])
        self.graph.points_changed.connect(self._graph_changed)
        self.stack.addWidget(self.slider_page)
        self.stack.addWidget(self.graph)
        root.addWidget(self.stack, 1)
        hint = QLabel("Gain en dB · clic dans le graphe pour ajouter un point · clic droit sur un point pour le supprimer")
        hint.setStyleSheet("color: #7a6840; font-size: 11px;")
        root.addWidget(hint)

    def apply_config(self, config):
        self.config = normalise_equalizer_config(config)
        self.preset.blockSignals(True)
        self.preset.clear()
        self.preset.addItems(self.config["presets"])
        self.preset.setCurrentText(self.config["current_preset"])
        self.preset.blockSignals(False)
        self.enabled.setChecked(self.config["enabled"])
        self.mode.blockSignals(True)
        self.mode.setCurrentIndex(1 if self.config["mode"] == "free" else 0)
        self.mode.blockSignals(False)
        self.stack.setCurrentIndex(1 if self.config["mode"] == "free" else 0)
        self._load_points(self.config["frequencies"], self.config["gains"])
        if self.config["mode"] == "free":
            self.graph.set_points(self.config["free_frequencies"], self.config["free_gains"])

    def set_theme_colors(self, colors: dict):
        self.graph.set_theme_colors(colors)

    def _load_points(self, frequencies, gains):
        self._sliders.clear()
        while self._slider_layout.count():
            item = self._slider_layout.takeAt(0)
            column = item.layout()
            if column is not None:
                while column.count():
                    child = column.takeAt(0)
                    if child.widget() is not None:
                        child.widget().deleteLater()
        for frequency, gain in zip(frequencies, gains):
            column = QVBoxLayout()
            freq_label = QLabel(f"{frequency:g}")
            freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label = QLabel(f"{gain:+.1f}")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slider = EqualizerSlider(Qt.Orientation.Vertical)
            slider.setRange(-120, 120)
            slider.setValue(round(gain * 10))
            slider.setToolTip(f"{frequency:g} Hz")
            slider.valueChanged.connect(self._sliders_changed)
            slider.reset_requested.connect(self._sliders_changed)
            column.addWidget(value_label)
            column.addWidget(slider, 1, Qt.AlignmentFlag.AlignHCenter)
            column.addWidget(freq_label)
            self._slider_layout.addLayout(column)
            self._sliders.append((slider, value_label, freq_label))
        self.graph.set_points(frequencies, gains)

    def _sliders_changed(self):
        gains = [slider.value() / 10 for slider, _, _ in self._sliders]
        for slider, label, _ in self._sliders:
            label.setText(f"{slider.value() / 10:+.1f}")
        self.graph.set_points(self.config["frequencies"], gains)
        self.config["gains"] = gains
        if self.config["mode"] == "bands":
            self.config["free_frequencies"] = list(self.config["frequencies"])
            self.config["free_gains"] = list(gains)
        self._emit()

    def _graph_changed(self, points):
        self.config["free_frequencies"] = list(points["frequencies"])
        self.config["free_gains"] = list(points["gains"])
        self._emit()

    def _mode_changed(self, index):
        self.stack.setCurrentIndex(index)
        self.config["mode"] = "free" if index == 1 else "bands"
        if self.config["mode"] == "free":
            self.graph.set_points(self.config["free_frequencies"], self.config["free_gains"])
        else:
            self.graph.set_points(self.config["frequencies"], self.config["gains"])
        self._emit()

    def _preset_selected(self, name):
        if name in self.config["presets"]:
            gains = self.config["presets"][name]
            if len(gains) == len(self.config["frequencies"]):
                self.config["gains"] = list(gains)
                self.config["current_preset"] = name
                self.config["free_frequencies"] = list(self.config["frequencies"])
                self.config["free_gains"] = list(gains)
                self._load_points(self.config["frequencies"], gains)
                self._emit()

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Nouveau preset", "Nom du preset :")
        if ok and name.strip():
            name = name.strip()
            self.config["presets"][name] = list(self.config["gains"])
            if self.preset.findText(name) < 0:
                self.preset.addItem(name)
            self.preset.setCurrentText(name)
            self.config["current_preset"] = name
            self._emit()

    def _delete_preset(self):
        name = self.preset.currentText()
        if name in DEFAULT_PRESETS:
            QMessageBox.information(self, "Preset intégré", "Les presets intégrés ne peuvent pas être supprimés.")
            return
        self.config["presets"].pop(name, None)
        self.preset.removeItem(self.preset.currentIndex())
        self.preset.setCurrentText("Plat")
        self._emit()

    def _emit(self):
        self.config_changed.emit(deepcopy(self.config))
