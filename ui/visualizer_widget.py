"""
Widget d'animation audio réactive « Solar Flow »
Vague fluide en tons jaune-orangé, synchronisée avec la musique en cours.
Désactivable (clic droit ou via le menu Affichage) pour préserver les performances.
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QSizePolicy, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPainterPath, QLinearGradient, QRadialGradient, QColor, QPen, QBrush
)

N_BANDS = 100
FPS_INTERVAL_MS = 33  # ~30 fps — fluide sans peser sur le CPU

# Palette solaire, cohérente avec le thème SolarSound
COL_FLARE = QColor(0xff, 0xe0, 0x8a)
COL_AMBER = QColor(0xf5, 0xc8, 0x42)
COL_ORANGE = QColor(0xf5, 0xa6, 0x23)
COL_EMBER = QColor(0xd9, 0x72, 0x0a)


class SolarVisualizer(QWidget):
    """
    Bandeau d'animation fluide réagissant au spectre audio.
    `levels_provider` est un callable sans argument renvoyant N_BANDS
    valeurs flottantes (0.0 → 1.0) — typiquement AudioEngine.get_visual_levels.
    """

    toggled = pyqtSignal(bool)

    def __init__(self, levels_provider=None, parent=None):
        super().__init__(parent)
        self._levels_provider = levels_provider
        self._smoothed = np.zeros(N_BANDS, dtype=np.float32)
        self._phase = 0.0
        self._enabled = True

        self.setMinimumHeight(90)
        self.setMaximumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setToolTip("Animation solaire — clic droit pour activer / désactiver")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(30)
        glow.setOffset(0, 0)
        glow.setColor(QColor(0xf5, 0xa6, 0x23, 150))
        self.setGraphicsEffect(glow)

        self._timer = QTimer(self)
        self._timer.setInterval(FPS_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ══════════════════════════════════════════════════════════════
    # Activation / désactivation (bouton perf)
    # ══════════════════════════════════════════════════════════════
    def set_enabled_animation(self, enabled: bool, emit: bool = True):
        self._enabled = enabled
        if enabled:
            self._timer.start()
        else:
            self._timer.stop()
            self._smoothed[:] = 0.0
        self.update()
        if emit:
            self.toggled.emit(enabled)

    def is_animation_enabled(self) -> bool:
        return self._enabled

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.set_enabled_animation(not self._enabled)
        super().mousePressEvent(event)

    # ══════════════════════════════════════════════════════════════
    # Boucle d'animation
    # ══════════════════════════════════════════════════════════════
    def _tick(self):
        if not self.isVisible():
            return

        raw = self._levels_provider() if self._levels_provider else None
        if raw is None or len(raw) == 0:
            raw = np.zeros(len(self._smoothed) or N_BANDS, dtype=np.float32)
        else:
            raw = np.asarray(raw, dtype=np.float32)

        # Le tableau lissé s'adapte à la taille reçue (peu importe N_BANDS
        # côté widget vs. n_bands côté moteur — évite tout désalignement).
        if len(raw) != len(self._smoothed):
            self._smoothed = np.zeros(len(raw), dtype=np.float32)

        # Lissage attaque/chute pour un mouvement fluide et « organique »
        attack, decay = 0.75, 0.18
        rising = raw > self._smoothed
        self._smoothed = np.where(
            rising,
            self._smoothed + (raw - self._smoothed) * attack,
            self._smoothed + (raw - self._smoothed) * decay,
        )

        self._phase += 0.045
        self.update()

    # ══════════════════════════════════════════════════════════════
    # Rendu
    # ══════════════════════════════════════════════════════════════
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        if w <= 4 or h <= 4:
            return

        # Panneau de fond à coins arrondis — tout le reste (halo, vague)
        # est ensuite dessiné à l'intérieur (clip) pour garder des bords
        # bien nets et ronds, y compris sous la vague.
        radius = max(22.0, h * 0.5)
        bg_path = QPainterPath()
        bg_path.addRoundedRect(0.0, 0.0, float(w), float(h), radius, radius)

        bg_grad = QLinearGradient(0, 0, 0, h)
        bg_top = QColor(0x1e, 0x1a, 0x12, 130)
        bg_bot = QColor(0x14, 0x11, 0x0a, 150)
        bg_grad.setColorAt(0.0, bg_top)
        bg_grad.setColorAt(1.0, bg_bot)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_grad))
        painter.drawPath(bg_path)

        painter.save()
        painter.setClipPath(bg_path)

        if not self._enabled:
            self._paint_idle_line(painter, w, h)
            painter.restore()
            return

        mid_y = h * 0.60
        bass = float(np.mean(self._smoothed[:6]))
        active = float(np.max(self._smoothed))

        # Halo radial qui respire avec les basses
        halo_alpha = int(26 + 90 * min(1.0, bass))
        radial = QRadialGradient(w * 0.5, mid_y, w * 0.55)
        c1 = QColor(COL_ORANGE); c1.setAlpha(halo_alpha)
        c2 = QColor(COL_ORANGE); c2.setAlpha(0)
        radial.setColorAt(0.0, c1)
        radial.setColorAt(1.0, c2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(radial))
        painter.drawRect(self.rect())

        # Onde de fond douce si pas de musique active (idle "respiration")
        n = max(2, len(self._smoothed))
        xs = np.linspace(6, w - 6, n)
        idle_wave = 0.05 + 0.035 * np.sin(np.linspace(0, 3.0 * np.pi, n) + self._phase)
        levels = self._smoothed if active > 0.03 else idle_wave.astype(np.float32)

        amp = (h * 0.4) - 3
        top_pts = [QPointF(x, mid_y - lv * amp) for x, lv in zip(xs, levels)]
        bot_pts = [QPointF(x, mid_y + lv * amp * 0.65) for x, lv in zip(xs, levels)]

        top_curve = self._smooth_path(top_pts)
        bot_curve = self._smooth_path(list(reversed(bot_pts)))

        # Remplissage : contour haut lissé + contour bas lissé (même
        # traitement arrondi des deux côtés, plus de piquant en bas).
        fill_path = QPainterPath(top_curve)
        fill_path.connectPath(bot_curve)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, mid_y - amp, 0, mid_y + amp * 0.5)
        c_top = QColor(COL_FLARE); c_top.setAlpha(215)
        c_mid = QColor(COL_AMBER); c_mid.setAlpha(190)
        c_bot = QColor(COL_EMBER); c_bot.setAlpha(150)
        grad.setColorAt(0.0, c_top)
        grad.setColorAt(0.55, c_mid)
        grad.setColorAt(1.0, c_bot)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPath(fill_path)

        pen_top = QPen(COL_FLARE, 1.6)
        pen_top.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen_top.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen_top)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(top_curve)

        pen_bot = QPen(COL_EMBER, 1.2)
        pen_bot.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen_bot.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen_bot)
        painter.drawPath(bot_curve)

        painter.restore()

    def _paint_idle_line(self, painter, w, h):
        """Affichage minimal quand l'animation est désactivée (mode perf)."""
        y = h * 0.62
        pen = QPen(QColor(0x5a, 0x4a, 0x28), 1.2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(6, y), QPointF(w - 6, y))
        painter.setPen(QColor(0x5a, 0x4a, 0x28))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Animation désactivée")

    @staticmethod
    def _smooth_path(points) -> QPainterPath:
        """Construit une courbe fluide passant par les points (quadratiques enchaînées)."""
        path = QPainterPath()
        path.moveTo(points[0])
        for i in range(1, len(points) - 1):
            p0 = points[i]
            p1 = points[i + 1]
            mid = QPointF((p0.x() + p1.x()) / 2.0, (p0.y() + p1.y()) / 2.0)
            path.quadTo(p0, mid)
        path.lineTo(points[-1])
        return path
