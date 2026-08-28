"""
Panneau de rotation orbitale SolarSound
Contrôle la rotation du son autour des 4 enceintes (FL → FR → SR → SL → FL).
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QSlider, QCheckBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QRadialGradient, QFont, QPainterPath

try:
    from ..audio.engine import SpatialConfig
except (ImportError, ModuleNotFoundError):
    from audio.engine import SpatialConfig


# ── Visualiseur du champ sonore rotatif ───────────────────────────────────────

class RotationVisualizer(QWidget):
    """
    Vue du dessus de la pièce avec les 4 enceintes.
    Affiche l'angle courant de L (orange) et R (blanc, opposé).
    """
    SPEAKER_LABELS = ["FL", "FR", "SR", "SL"]
    SPEAKER_ANGLES_DEG = [135, 45, 315, 225]  # angles visuels (vue du dessus, sens trigo)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self.setMaximumSize(220, 220)
        self._angle = 0.0
        self._spread = 0.5
        self._enabled = False
        self._separation = 1.0

    def update_state(self, angle_rad: float, spread: float, enabled: bool, separation: float = 1.0):
        self._angle = angle_rad
        self._spread = spread
        self._enabled = enabled
        self._separation = separation
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 20

        # ── Fond ──────────────────────────────────────────────────────
        p.fillRect(self.rect(), QColor("#0f0d0a"))

        if not self._enabled:
            p.setPen(QColor("#3d3420"))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "ROTATION\nDÉSACTIVÉE")
            return

        # ── Cercle de fond ─────────────────────────────────────────────
        p.setPen(QPen(QColor("#2a2416"), 1))
        p.setBrush(QColor("#1a1508"))
        p.drawEllipse(QPointF(cx, cy), r, r)

        # ── Quadrants repère ───────────────────────────────────────────
        p.setPen(QPen(QColor("#2a2416"), 1, Qt.PenStyle.DashLine))
        p.drawLine(int(cx - r), int(cy), int(cx + r), int(cy))
        p.drawLine(int(cx), int(cy - r), int(cx), int(cy + r))

        # ── Halo rotatif L (orange) ────────────────────────────────────
        # L'angle visuel : 0 = haut (FL), tourne dans le sens des aiguilles
        angle_L_visual = -self._angle  # inversé car Qt mesure depuis la droite
        self._draw_halo(p, cx, cy, r, angle_L_visual, QColor("#f5a623"), self._spread)

        # ── Halo rotatif R (blanc/bleu) — décalé selon la séparation ────
        angle_R_visual = angle_L_visual + math.pi * self._separation
        self._draw_halo(p, cx, cy, r, angle_R_visual, QColor("#7ecfcf"), self._spread)

        # ── Enceintes ──────────────────────────────────────────────────
        for label, deg in zip(self.SPEAKER_LABELS, self.SPEAKER_ANGLES_DEG):
            rad = math.radians(deg)
            sx = cx + r * math.cos(rad)
            sy = cy - r * math.sin(rad)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#3d3420"))
            p.drawEllipse(QPointF(sx, sy), 10, 10)

            p.setPen(QColor("#f5a623"))
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            # Décaler le label vers l'extérieur
            lx = cx + (r + 14) * math.cos(rad)
            ly = cy - (r + 14) * math.sin(rad)
            p.drawText(int(lx - 12), int(ly - 8), 24, 16,
                       Qt.AlignmentFlag.AlignCenter, label)

        # ── Point central ──────────────────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#3d3420"))
        p.drawEllipse(QPointF(cx, cy), 4, 4)

    def _draw_halo(self, p, cx, cy, r, angle_rad, color, spread):
        """Dessine un halo directionnel représentant la source sonore."""
        # Position du point lumineux sur le cercle
        px = cx + r * 0.72 * math.cos(angle_rad)
        py = cy - r * 0.72 * math.sin(angle_rad)

        # Taille du halo en fonction de l'étalement
        halo_r = int(r * (0.2 + spread * 0.45))

        grad = QRadialGradient(QPointF(px, py), halo_r)
        c0 = QColor(color)
        c0.setAlpha(180)
        c1 = QColor(color)
        c1.setAlpha(0)
        grad.setColorAt(0.0, c0)
        grad.setColorAt(1.0, c1)

        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(px, py), halo_r, halo_r)

        # Point central lumineux
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(px, py), 5, 5)


# ── Panneau complet ───────────────────────────────────────────────────────────

class RotationPanel(QWidget):
    """Panneau de contrôle de la rotation orbitale"""
    config_changed = pyqtSignal(SpatialConfig)

    def __init__(self, config: SpatialConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._anim_angle = 0.0

        # Timer d'animation du visualiseur (indépendant du vrai angle audio)
        self._anim_timer = QTimer()
        self._anim_timer.setInterval(33)  # ~30fps
        self._anim_timer.timeout.connect(self._tick_animation)

        self._setup_ui()
        self._connect_signals()
        self._update_enabled_state()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(12)

        # ── Activation ────────────────────────────────────────────────
        header = QHBoxLayout()
        self.chk_enable = QCheckBox("Activer la rotation orbitale")
        self.chk_enable.setChecked(self.config.rotation_enabled)
        font = self.chk_enable.font()
        font.setBold(True)
        self.chk_enable.setFont(font)
        header.addWidget(self.chk_enable)
        header.addStretch()
        main.addLayout(header)

        # ── Zone centrale : visualiseur + contrôles ───────────────────
        center = QHBoxLayout()
        center.setSpacing(16)

        # Visualiseur
        self.visualizer = RotationVisualizer()
        center.addWidget(self.visualizer, alignment=Qt.AlignmentFlag.AlignCenter)

        # Contrôles
        controls = QVBoxLayout()
        controls.setSpacing(14)

        # Vitesse
        speed_grp = QGroupBox("VITESSE DE ROTATION")
        speed_layout = QVBoxLayout(speed_grp)
        speed_layout.setSpacing(6)

        speed_row = QHBoxLayout()
        self.lbl_speed = QLabel(self._fmt_speed(self.config.rotation_speed))
        self.lbl_speed.setFixedWidth(70)
        self.lbl_speed.setStyleSheet("color: #f5a623; font-family: Consolas; font-size: 12px;")

        self.sld_speed = QSlider(Qt.Orientation.Horizontal)
        self.sld_speed.setRange(1, 200)   # 0.01 → 2.00 tours/s (×100)
        self.sld_speed.setValue(int(self.config.rotation_speed * 100))
        speed_row.addWidget(self.sld_speed)
        speed_row.addWidget(self.lbl_speed)
        speed_layout.addLayout(speed_row)

        # Presets vitesse
        presets_row = QHBoxLayout()
        presets_row.setSpacing(4)
        for label, val in [("Lent", 5), ("Moyen", 20), ("Rapide", 80)]:
            btn = QPushButton(label)
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda _, v=val: self._set_speed_preset(v))
            presets_row.addWidget(btn)
        speed_layout.addLayout(presets_row)

        controls.addWidget(speed_grp)

        # Étalement
        spread_grp = QGroupBox("ÉTALEMENT ANGULAIRE")
        spread_layout = QVBoxLayout(spread_grp)
        spread_layout.setSpacing(6)

        spread_row = QHBoxLayout()
        self.lbl_spread = QLabel(self._fmt_spread(self.config.rotation_spread))
        self.lbl_spread.setFixedWidth(70)
        self.lbl_spread.setStyleSheet("color: #f5a623; font-family: Consolas; font-size: 12px;")

        self.sld_spread = QSlider(Qt.Orientation.Horizontal)
        self.sld_spread.setRange(0, 100)
        self.sld_spread.setValue(int(self.config.rotation_spread * 100))
        spread_row.addWidget(self.sld_spread)
        spread_row.addWidget(self.lbl_spread)
        spread_layout.addLayout(spread_row)

        hint = QLabel("0 % = 1 enceinte   /   100 % = 3 enceintes")
        self._rotation_hints = hint
        hint.setStyleSheet("font-size: 10px; color: #5a4a28;")
        spread_layout.addWidget(hint)

        controls.addWidget(spread_grp)

        # Angle de séparation L/R
        angle_grp = QGroupBox("ANGLE ENTRE L ET R")
        angle_layout = QVBoxLayout(angle_grp)
        angle_layout.setSpacing(6)

        angle_row = QHBoxLayout()
        self.lbl_angle = QLabel(self._fmt_angle(self.config.stereo_separation))
        self.lbl_angle.setFixedWidth(40)
        self.lbl_angle.setStyleSheet("color: #f5a623; font-family: Consolas; font-size: 12px;")

        self.sld_angle = QSlider(Qt.Orientation.Horizontal)
        self.sld_angle.setRange(0, 100)
        self.sld_angle.setValue(int(self.config.stereo_separation * 100))
        self.sld_angle.setToolTip("0°=mono (sources fusionnées), 180°=stéréo opposé")
        angle_row.addWidget(self.sld_angle)
        angle_row.addWidget(self.lbl_angle)
        angle_layout.addLayout(angle_row)

        angle_hint = QLabel("0° = mono   /   180° = opposé (défaut)")
        self._angle_hint = angle_hint
        angle_hint.setStyleSheet("font-size: 10px; color: #5a4a28;")
        angle_layout.addWidget(angle_hint)

        controls.addWidget(angle_grp)
        controls.addStretch()

        center.addLayout(controls, stretch=1)
        main.addLayout(center)

        # ── Explication ───────────────────────────────────────────────
        info = QLabel(
            "🔶 La source gauche (orange) tourne en continu autour des 4 enceintes.\n"
            "🔷 La source droite (bleu) reste à l'opposé exact."
        )
        self._rotation_info = info
        info.setStyleSheet("font-size: 11px; color: #7a6840; line-height: 1.4;")
        info.setWordWrap(True)
        main.addWidget(info)

    def _connect_signals(self):
        self.chk_enable.toggled.connect(self._on_enable_toggled)
        self.sld_speed.valueChanged.connect(self._on_speed_changed)
        self.sld_spread.valueChanged.connect(self._on_spread_changed)
        self.sld_angle.valueChanged.connect(self._on_angle_changed)

    def set_theme_colors(self, colors: dict):
        accent = colors.get("accent", "#f5a623")
        muted = colors.get("text_muted", "#5a4a28")
        secondary = colors.get("text_secondary", "#7a6840")
        for label in (self.lbl_speed, self.lbl_spread, self.lbl_angle):
            label.setStyleSheet(f"color: {accent}; font-family: Consolas; font-size: 12px;")
        self._rotation_hints.setStyleSheet(f"font-size: 10px; color: {muted};")
        self._angle_hint.setStyleSheet(f"font-size: 10px; color: {muted};")
        self._rotation_info.setStyleSheet(f"font-size: 11px; color: {secondary}; line-height: 1.4;")

    # ── Handlers ─────────────────────────────────────────────────────
    def _on_enable_toggled(self, checked: bool):
        self.config.rotation_enabled = checked
        self._update_enabled_state()
        if checked:
            self._anim_timer.start()
        else:
            self._anim_timer.stop()
            self.visualizer.update_state(0.0, self.config.rotation_spread, False)
        self.config_changed.emit(self.config)

    def _on_speed_changed(self, val: int):
        self.config.rotation_speed = val / 100.0
        self.lbl_speed.setText(self._fmt_speed(self.config.rotation_speed))
        self.config_changed.emit(self.config)

    def _on_spread_changed(self, val: int):
        self.config.rotation_spread = val / 100.0
        self.lbl_spread.setText(self._fmt_spread(self.config.rotation_spread))
        self.visualizer.update_state(self._anim_angle, self.config.rotation_spread,
                                      self.config.rotation_enabled,
                                      self.config.stereo_separation)
        self.config_changed.emit(self.config)

    def _on_angle_changed(self, val: int):
        self.config.stereo_separation = val / 100.0
        self.lbl_angle.setText(self._fmt_angle(self.config.stereo_separation))
        self.visualizer.update_state(self._anim_angle, self.config.rotation_spread,
                                      self.config.rotation_enabled,
                                      self.config.stereo_separation)
        self.config_changed.emit(self.config)

    def _set_speed_preset(self, val: int):
        self.sld_speed.setValue(val)

    def _update_enabled_state(self):
        enabled = self.config.rotation_enabled
        self.sld_speed.setEnabled(enabled)
        self.sld_spread.setEnabled(enabled)
        self.sld_angle.setEnabled(enabled)
        if enabled and not self._anim_timer.isActive():
            self._anim_timer.start()
        elif not enabled:
            self._anim_timer.stop()

    def _tick_animation(self):
        """Anime le visualiseur à 30fps (indépendant du vrai moteur audio)"""
        dt = 0.033  # ~30fps
        self._anim_angle = (self._anim_angle + 2 * math.pi * self.config.rotation_speed * dt) % (2 * math.pi)
        self.visualizer.update_state(self._anim_angle, self.config.rotation_spread,
                                      self.config.rotation_enabled,
                                      self.config.stereo_separation)

    # ── Formatage ─────────────────────────────────────────────────────
    @staticmethod
    def _fmt_angle(v: float) -> str:
        return f"{int(v * 180)}°"

    @staticmethod
    def _fmt_speed(v: float) -> str:
        if v < 0.1:
            return f"{v*60:.1f} tr/min"
        return f"{v:.2f} tr/s"

    @staticmethod
    def _fmt_spread(v: float) -> str:
        return f"{int(v * 100)} %"

    def apply_config(self, config: SpatialConfig):
        self.config = config
        self.chk_enable.setChecked(config.rotation_enabled)
        self.sld_speed.setValue(int(config.rotation_speed * 100))
        self.sld_spread.setValue(int(config.rotation_spread * 100))
        self.sld_angle.setValue(int(config.stereo_separation * 100))
        self._update_enabled_state()
