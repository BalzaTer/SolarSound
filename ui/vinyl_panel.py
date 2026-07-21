"""
Panneau d'effet vinyle SolarSound
Contrôles : vitesse moteur, wow/flutter, aléatoire, crépitements, hiss.
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QSlider, QCheckBox, QPushButton, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QBrush

try:
    from ..audio.vinyl import VinylConfig
except (ImportError, ModuleNotFoundError):
    from audio.vinyl import VinylConfig


# ── Visualiseur de la courbe de vitesse ──────────────────────────────────────

class WowFlutterViz(QWidget):
    """Affiche la courbe de vitesse simulée (wow+flutter) en temps réel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        self.setMinimumWidth(200)
        self._config = VinylConfig()
        self._phase = 0.0
        self._history = [1.0] * 200

        self._timer = QTimer()
        self._timer.setInterval(40)  # 25fps
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def update_config(self, cfg: VinylConfig):
        self._config = cfg

    def _tick(self):
        cfg = self._config
        dt = 0.04  # ~25fps
        self._phase += dt
        wow = cfg.wow_amount * math.sin(2 * math.pi * cfg.wow_rate * self._phase)
        flutter = cfg.flutter_amount * math.sin(2 * math.pi * cfg.flutter_rate * self._phase)
        speed = cfg.motor_speed + wow + flutter
        self._history.append(max(0.1, speed))
        if len(self._history) > 200:
            self._history.pop(0)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Fond
        p.fillRect(self.rect(), QColor("#0c0a07"))

        # Ligne de référence (vitesse 1.0)
        cfg = self._config
        y_center = h / 2
        p.setPen(QPen(QColor("#2a2416"), 1, Qt.PenStyle.DashLine))
        p.drawLine(0, int(y_center), w, int(y_center))

        # Valeur actuelle
        if self._history:
            last = self._history[-1]
            pct = (last - 1.0)
            label = f"{last:.4f}x"
            p.setPen(QColor("#7a6840"))
            p.setFont(QFont("Consolas", 8))
            p.drawText(4, 14, label)

        if not cfg.enabled:
            p.setPen(QColor("#3d3420"))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "désactivé")
            return

        # Courbe de vitesse
        if len(self._history) < 2:
            return

        # Calcul de la plage pour le scaling
        speed_range = max(0.001, cfg.wow_amount + cfg.flutter_amount) * 2.5
        v_scale = (h * 0.4) / speed_range

        n = len(self._history)
        pts = []
        for i, v in enumerate(self._history):
            x = int(i * w / n)
            y = int(y_center - (v - cfg.motor_speed) * v_scale)
            y = max(2, min(h - 2, y))
            pts.append((x, y))

        # Dégradé orange pour la courbe
        p.setPen(QPen(QColor("#f5a623"), 1.5))
        for i in range(1, len(pts)):
            p.drawLine(pts[i-1][0], pts[i-1][1], pts[i][0], pts[i][1])

        # Point courant
        if pts:
            px, py = pts[-1]
            p.setBrush(QColor("#f5a623"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(px - 3, py - 3, 6, 6)


# ── Panneau complet ──────────────────────────────────────────────────────────

class VinylPanel(QWidget):
    config_changed = pyqtSignal(VinylConfig)

    def __init__(self, vinyl_config: VinylConfig, parent=None):
        super().__init__(parent)
        self.config = vinyl_config
        self._setup_ui()
        self._connect_signals()
        self._update_enabled_state()

    # ── Construction UI ───────────────────────────────────────────────

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(10)

        # ── Activation ─────────────────────────────────────────────
        header = QHBoxLayout()
        self.chk_enable = QCheckBox("Activer l'effet vinyle")
        f = self.chk_enable.font(); f.setBold(True); self.chk_enable.setFont(f)
        self.chk_enable.setChecked(self.config.enabled)
        header.addWidget(self.chk_enable)

        # Presets
        header.addStretch()
        for label, method in [("Neuf", self._preset_new),
                               ("Usé", self._preset_worn),
                               ("Très usé", self._preset_damaged)]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.clicked.connect(method)
            header.addWidget(btn)
        main.addLayout(header)

        # ── Visualiseur ─────────────────────────────────────────────
        self.viz = WowFlutterViz()
        self.viz.update_config(self.config)
        main.addWidget(self.viz)

        # ── Grille de contrôles ─────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(1, 1)

        # ── COLONNE GAUCHE : Moteur ────────────────────────────────
        motor_grp = QGroupBox("MOTEUR")
        motor_layout = QVBoxLayout(motor_grp)
        motor_layout.setSpacing(8)

        self._add_slider(motor_layout, "Vitesse :",
                         1, 200, int(self.config.motor_speed * 100),
                         lambda v: self._set("motor_speed", v / 100.0),
                         fmt=lambda v: f"{v/100:.2f}x",
                         attr="sld_speed", lbl="lbl_speed")

        self._add_slider(motor_layout, "Aléatoire :",
                         0, 100, int(self.config.motor_random * 5000),
                         lambda v: self._set("motor_random", v / 5000.0),
                         fmt=lambda v: f"{v/50:.1f}%",
                         attr="sld_random", lbl="lbl_random")

        grid.addWidget(motor_grp, 0, 0)

        # ── COLONNE DROITE : Wow & Flutter ─────────────────────────
        wf_grp = QGroupBox("WOW & FLUTTER")
        wf_layout = QVBoxLayout(wf_grp)
        wf_layout.setSpacing(8)

        self._add_slider(wf_layout, "Wow (amplitude) :",
                         0, 100, int(self.config.wow_amount * 5000),
                         lambda v: self._set("wow_amount", v / 5000.0),
                         fmt=lambda v: f"{v/50:.1f}%",
                         attr="sld_wow_amt", lbl="lbl_wow_amt")

        self._add_slider(wf_layout, "Wow (fréquence) :",
                         5, 300, int(self.config.wow_rate * 100),
                         lambda v: self._set("wow_rate", v / 100.0),
                         fmt=lambda v: f"{v/100:.2f} Hz",
                         attr="sld_wow_rate", lbl="lbl_wow_rate")

        self._add_slider(wf_layout, "Flutter (amplitude) :",
                         0, 100, int(self.config.flutter_amount * 10000),
                         lambda v: self._set("flutter_amount", v / 10000.0),
                         fmt=lambda v: f"{v/100:.2f}%",
                         attr="sld_flutter_amt", lbl="lbl_flutter_amt")

        self._add_slider(wf_layout, "Flutter (fréquence) :",
                         100, 2000, int(self.config.flutter_rate * 100),
                         lambda v: self._set("flutter_rate", v / 100.0),
                         fmt=lambda v: f"{v/100:.1f} Hz",
                         attr="sld_flutter_rate", lbl="lbl_flutter_rate")

        grid.addWidget(wf_grp, 0, 1)

        main.addLayout(grid)

        # ── Crépitements ────────────────────────────────────────────
        crackle_grp = QGroupBox("CRÉPITEMENTS & BRUIT DE FOND")
        crackle_layout = QGridLayout(crackle_grp)
        crackle_layout.setSpacing(8)
        crackle_layout.setColumnStretch(1, 1)
        crackle_layout.setColumnStretch(3, 1)

        self._add_grid_slider(crackle_layout, 0, "Densité (clics/s) :",
                               0, 300, int(self.config.crackle_density),
                               lambda v: self._set("crackle_density", float(v)),
                               fmt=lambda v: f"{v}",
                               attr="sld_crackle_density", lbl="lbl_crackle_density")

        self._add_grid_slider(crackle_layout, 1, "Amplitude :",
                               0, 100, int(self.config.crackle_amplitude * 100),
                               lambda v: self._set("crackle_amplitude", v / 100.0),
                               fmt=lambda v: f"{v}%",
                               attr="sld_crackle_amp", lbl="lbl_crackle_amp")

        self._add_grid_slider(crackle_layout, 2, "Durée clic (ms) :",
                               1, 50, int(self.config.crackle_duration_ms * 2),
                               lambda v: self._set("crackle_duration_ms", v / 2.0),
                               fmt=lambda v: f"{v/2:.1f} ms",
                               attr="sld_crackle_dur", lbl="lbl_crackle_dur")

        self._add_grid_slider(crackle_layout, 3, "Bruit de fond (hiss) :",
                               0, 100, int(self.config.hiss_level * 5000),
                               lambda v: self._set("hiss_level", v / 5000.0),
                               fmt=lambda v: f"{v/50:.1f}%",
                               attr="sld_hiss", lbl="lbl_hiss")

        main.addWidget(crackle_grp)

    def _add_slider(self, layout, label_text, min_v, max_v, val,
                    callback, fmt, attr, lbl):
        row = QHBoxLayout()
        lbl_name = QLabel(label_text)
        lbl_name.setFixedWidth(150)
        lbl_name.setStyleSheet("font-size: 11px;")
        row.addWidget(lbl_name)

        sld = QSlider(Qt.Orientation.Horizontal)
        sld.setRange(min_v, max_v)
        sld.setValue(val)
        row.addWidget(sld)

        lbl_val = QLabel(fmt(val))
        lbl_val.setFixedWidth(55)
        lbl_val.setStyleSheet("color: #f5a623; font-family: Consolas; font-size: 11px;")
        row.addWidget(lbl_val)

        setattr(self, attr, sld)
        setattr(self, lbl, lbl_val)

        def on_change(v, cb=callback, f=fmt, l=lbl_val):
            l.setText(f(v))
            cb(v)

        sld.valueChanged.connect(on_change)
        layout.addLayout(row)

    def _add_grid_slider(self, layout, row_idx, label_text, min_v, max_v, val,
                         callback, fmt, attr, lbl):
        lbl_name = QLabel(label_text)
        lbl_name.setStyleSheet("font-size: 11px;")
        layout.addWidget(lbl_name, row_idx, 0)

        sld = QSlider(Qt.Orientation.Horizontal)
        sld.setRange(min_v, max_v)
        sld.setValue(val)
        layout.addWidget(sld, row_idx, 1)

        lbl_val = QLabel(fmt(val))
        lbl_val.setFixedWidth(55)
        lbl_val.setStyleSheet("color: #f5a623; font-family: Consolas; font-size: 11px;")
        layout.addWidget(lbl_val, row_idx, 2)

        setattr(self, attr, sld)
        setattr(self, lbl, lbl_val)

        def on_change(v, cb=callback, f=fmt, l=lbl_val):
            l.setText(f(v))
            cb(v)

        sld.valueChanged.connect(on_change)

    # ── Signals ───────────────────────────────────────────────────────

    def _connect_signals(self):
        self.chk_enable.toggled.connect(self._on_enable)

    def _on_enable(self, checked: bool):
        self.config.enabled = checked
        self._update_enabled_state()
        if checked:
            self.viz.start()
        else:
            self.viz.stop()
            self.viz.update()
        self.config_changed.emit(self.config)

    def _set(self, attr: str, value):
        setattr(self.config, attr, value)
        self.viz.update_config(self.config)
        self.config_changed.emit(self.config)

    def _update_enabled_state(self):
        enabled = self.config.enabled
        widgets = [
            self.sld_speed, self.sld_random,
            self.sld_wow_amt, self.sld_wow_rate,
            self.sld_flutter_amt, self.sld_flutter_rate,
            self.sld_crackle_density, self.sld_crackle_amp,
            self.sld_crackle_dur, self.sld_hiss,
        ]
        for w in widgets:
            w.setEnabled(enabled)
        if enabled and not self.viz._timer.isActive():
            self.viz.start()
        elif not enabled:
            self.viz.stop()

    # ── Presets ───────────────────────────────────────────────────────

    def _apply_preset(self, cfg_values: dict):
        for k, v in cfg_values.items():
            setattr(self.config, k, v)
        self._refresh_all_sliders()
        self.viz.update_config(self.config)
        self.config_changed.emit(self.config)

    def _preset_new(self):
        self._apply_preset({
            "motor_speed": 1.0, "motor_random": 0.0005,
            "wow_amount": 0.001, "wow_rate": 0.6,
            "flutter_amount": 0.0003, "flutter_rate": 6.0,
            "crackle_density": 5.0, "crackle_amplitude": 0.04,
            "crackle_duration_ms": 2.0, "hiss_level": 0.001,
        })

    def _preset_worn(self):
        self._apply_preset({
            "motor_speed": 1.0, "motor_random": 0.002,
            "wow_amount": 0.004, "wow_rate": 0.8,
            "flutter_amount": 0.001, "flutter_rate": 8.0,
            "crackle_density": 40.0, "crackle_amplitude": 0.08,
            "crackle_duration_ms": 3.5, "hiss_level": 0.004,
        })

    def _preset_damaged(self):
        self._apply_preset({
            "motor_speed": 0.98, "motor_random": 0.008,
            "wow_amount": 0.012, "wow_rate": 1.2,
            "flutter_amount": 0.004, "flutter_rate": 10.0,
            "crackle_density": 150.0, "crackle_amplitude": 0.18,
            "crackle_duration_ms": 6.0, "hiss_level": 0.010,
        })

    def _refresh_all_sliders(self):
        """Remet à jour tous les sliders depuis self.config (après preset/session)."""
        cfg = self.config
        pairs = [
            (self.sld_speed,           int(cfg.motor_speed * 100)),
            (self.sld_random,          int(cfg.motor_random * 5000)),
            (self.sld_wow_amt,         int(cfg.wow_amount * 5000)),
            (self.sld_wow_rate,        int(cfg.wow_rate * 100)),
            (self.sld_flutter_amt,     int(cfg.flutter_amount * 10000)),
            (self.sld_flutter_rate,    int(cfg.flutter_rate * 100)),
            (self.sld_crackle_density, int(cfg.crackle_density)),
            (self.sld_crackle_amp,     int(cfg.crackle_amplitude * 100)),
            (self.sld_crackle_dur,     int(cfg.crackle_duration_ms * 2)),
            (self.sld_hiss,            int(cfg.hiss_level * 5000)),
        ]
        for sld, val in pairs:
            sld.blockSignals(True)
            sld.setValue(max(sld.minimum(), min(sld.maximum(), val)))
            sld.blockSignals(False)
        # Refresh labels
        self.lbl_speed.setText(f"{cfg.motor_speed:.2f}x")
        self.lbl_random.setText(f"{cfg.motor_random * 5000 / 50:.1f}%")
        self.lbl_wow_amt.setText(f"{cfg.wow_amount * 5000 / 50:.1f}%")
        self.lbl_wow_rate.setText(f"{cfg.wow_rate:.2f} Hz")
        self.lbl_flutter_amt.setText(f"{cfg.flutter_amount * 10000 / 100:.2f}%")
        self.lbl_flutter_rate.setText(f"{cfg.flutter_rate:.1f} Hz")
        self.lbl_crackle_density.setText(f"{int(cfg.crackle_density)}")
        self.lbl_crackle_amp.setText(f"{int(cfg.crackle_amplitude * 100)}%")
        self.lbl_crackle_dur.setText(f"{cfg.crackle_duration_ms:.1f} ms")
        self.lbl_hiss.setText(f"{cfg.hiss_level * 5000 / 50:.1f}%")

    def apply_config(self, cfg: VinylConfig):
        self.config = cfg
        self.chk_enable.setChecked(cfg.enabled)
        self._refresh_all_sliders()
        self._update_enabled_state()
        self.viz.update_config(cfg)
