"""
Panneau de spatialisation 5.1 — SolarSound
Sliders HORIZONTAUX par canal, disposition en grille 5.1 lisible.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QSlider, QCheckBox, QDoubleSpinBox, QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal

try:
    from ..audio.engine import SpatialConfig
except (ImportError, ModuleNotFoundError):
    from audio.engine import SpatialConfig


# ── Slider horizontal par canal ───────────────────────────────────────────────

class ChannelSlider(QWidget):
    """Slider HORIZONTAL avec label canal + valeur, sur une seule ligne."""
    value_changed = pyqtSignal(float)

    CHANNEL_COLORS = {
        "FL":  "#f5a623",
        "FR":  "#f5a623",
        "C":   "#e8d5a0",
        "LFE": "#ff6b35",
        "SL":  "#7ecfcf",
        "SR":  "#7ecfcf",
    }

    def __init__(self, name: str, initial: float = 1.0, parent=None):
        super().__init__(parent)
        self.name = name
        color = self.CHANNEL_COLORS.get(name, "#f5a623")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        # Étiquette canal (largeur fixe pour aligner)
        lbl_name = QLabel(name)
        lbl_name.setFixedWidth(30)
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_name.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {color};")
        layout.addWidget(lbl_name)

        # Slider horizontal
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 200)
        self.slider.setValue(int(initial * 100))
        self.slider.setToolTip(f"Canal {name} : {initial:.1f}")
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 5px; background: #2a2416; border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {color}; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {color}; border: 2px solid #0f0d0a;
                width: 14px; height: 14px;
                margin: -5px 0; border-radius: 7px;
            }}
        """)
        self.slider.valueChanged.connect(self._on_changed)
        layout.addWidget(self.slider, stretch=1)

        # Valeur numérique
        self.val_label = QLabel(f"{initial:.1f}")
        self.val_label.setFixedWidth(30)
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.val_label.setStyleSheet("font-size: 11px; color: #a08060; font-family: Consolas;")
        layout.addWidget(self.val_label)

    def _on_changed(self, value: int):
        v = value / 100.0
        self.val_label.setText(f"{v:.1f}")
        self.slider.setToolTip(f"Canal {self.name} : {v:.1f}")
        self.value_changed.emit(v)

    def get_value(self) -> float:
        return self.slider.value() / 100.0

    def set_value(self, v: float):
        self.slider.setValue(int(v * 100))


# ── Panneau complet ───────────────────────────────────────────────────────────

class SpatialPanel(QWidget):
    config_changed = pyqtSignal(SpatialConfig)

    def __init__(self, config: SpatialConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        main_layout = QVBoxLayout(inner)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # ── Canaux 5.1 ────────────────────────────────────────────────
        channels_group = QGroupBox("MIXAGE DES CANAUX 5.1")
        ch_layout = QVBoxLayout(channels_group)
        ch_layout.setSpacing(4)

        # Disposition 5.1 : chaque canal sur sa propre ligne
        # Groupe Avant
        lbl_front = QLabel("— AVANT —")
        self._lbl_front = lbl_front
        lbl_front.setStyleSheet("color: #5a4a28; font-size: 10px; letter-spacing: 3px;")
        lbl_front.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ch_layout.addWidget(lbl_front)

        self.ch_fl  = ChannelSlider("FL",  self.config.gain_fl)
        self.ch_c   = ChannelSlider("C",   self.config.gain_c)
        self.ch_fr  = ChannelSlider("FR",  self.config.gain_fr)
        ch_layout.addWidget(self.ch_fl)
        ch_layout.addWidget(self.ch_c)
        ch_layout.addWidget(self.ch_fr)

        # Séparateur
        lbl_surr = QLabel("— SURROUND + LFE —")
        self._lbl_surr = lbl_surr
        lbl_surr.setStyleSheet("color: #5a4a28; font-size: 10px; letter-spacing: 3px; margin-top: 4px;")
        lbl_surr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ch_layout.addWidget(lbl_surr)

        self.ch_sl  = ChannelSlider("SL",  self.config.gain_sl)
        self.ch_sr  = ChannelSlider("SR",  self.config.gain_sr)
        self.ch_lfe = ChannelSlider("LFE", self.config.gain_lfe)
        ch_layout.addWidget(self.ch_sl)
        ch_layout.addWidget(self.ch_sr)
        ch_layout.addWidget(self.ch_lfe)

        # Légende
        legend = QLabel("0.0 = muet  ·  1.0 = normal  ·  2.0 = amplifié")
        self._legend = legend
        legend.setStyleSheet("font-size: 10px; color: #3d3420;")
        legend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ch_layout.addWidget(legend)

        main_layout.addWidget(channels_group)

        # ── Doublement façade → surround ──────────────────────────────
        surround_group = QGroupBox("DOUBLEMENT FAÇADE → SURROUND")
        surr_layout = QVBoxLayout(surround_group)
        surr_layout.setSpacing(6)

        self.chk_double = QCheckBox("Copier le stéréo avant vers les enceintes surround")
        self.chk_double.setChecked(self.config.double_front_to_surround)
        surr_layout.addWidget(self.chk_double)

        blend_row = QHBoxLayout()
        blend_row.addWidget(QLabel("Ratio de mélange :"))
        self.sld_blend = QSlider(Qt.Orientation.Horizontal)
        self.sld_blend.setRange(0, 100)
        self.sld_blend.setValue(int(self.config.surround_blend * 100))
        self.sld_blend.setEnabled(self.config.double_front_to_surround)
        blend_row.addWidget(self.sld_blend)
        self.lbl_blend = QLabel(f"{self.config.surround_blend:.0%}")
        self.lbl_blend.setFixedWidth(40)
        self.lbl_blend.setStyleSheet("color: #f5a623; font-family: Consolas;")
        blend_row.addWidget(self.lbl_blend)
        surr_layout.addLayout(blend_row)
        main_layout.addWidget(surround_group)

        # ── Répartition selon la phase ──────────────────────────────
        phase_group = QGroupBox("EFFET PHASE : AVANT / ARRIÈRE")
        phase_layout = QVBoxLayout(phase_group)
        phase_layout.setSpacing(6)

        self.chk_phase = QCheckBox("Envoyer le signal hors phase vers les surrounds")
        self.chk_phase.setChecked(self.config.phase_to_surround)
        phase_layout.addWidget(self.chk_phase)

        phase_row = QHBoxLayout()
        phase_row.addWidget(QLabel("Intensité arrière :"))
        self.sld_phase = QSlider(Qt.Orientation.Horizontal)
        self.sld_phase.setRange(0, 100)
        self.sld_phase.setValue(int(self.config.phase_rear_blend * 100))
        self.sld_phase.setEnabled(self.config.phase_to_surround)
        phase_row.addWidget(self.sld_phase)
        self.lbl_phase = QLabel(f"{self.config.phase_rear_blend:.0%}")
        self.lbl_phase.setFixedWidth(40)
        self.lbl_phase.setStyleSheet("color: #f5a623; font-family: Consolas;")
        phase_row.addWidget(self.lbl_phase)
        phase_layout.addLayout(phase_row)
        main_layout.addWidget(phase_group)

        # ── Mixage LFE ────────────────────────────────────────────────
        lfe_group = QGroupBox("MIXAGE MONO → CAISSON DE BASSE (LFE)")
        lfe_layout = QGridLayout(lfe_group)
        lfe_layout.setSpacing(8)

        self.chk_lfe = QCheckBox("Activer le mixage mono vers le caisson")
        self.chk_lfe.setChecked(self.config.mix_to_lfe)
        lfe_layout.addWidget(self.chk_lfe, 0, 0, 1, 3)

        lfe_layout.addWidget(QLabel("Fréquence de coupure :"), 1, 0)
        self.spin_lpf = QDoubleSpinBox()
        self.spin_lpf.setRange(40.0, 300.0)
        self.spin_lpf.setSingleStep(5.0)
        self.spin_lpf.setValue(self.config.lfe_low_pass_hz)
        self.spin_lpf.setSuffix(" Hz")
        self.spin_lpf.setEnabled(self.config.mix_to_lfe)
        lfe_layout.addWidget(self.spin_lpf, 1, 1)

        lfe_layout.addWidget(QLabel("Gain LFE :"), 2, 0)
        self.sld_lfe_gain = QSlider(Qt.Orientation.Horizontal)
        self.sld_lfe_gain.setRange(0, 200)
        self.sld_lfe_gain.setValue(int(self.config.lfe_gain * 100))
        self.sld_lfe_gain.setEnabled(self.config.mix_to_lfe)
        lfe_layout.addWidget(self.sld_lfe_gain, 2, 1)
        self.lbl_lfe_gain = QLabel(f"{self.config.lfe_gain:.1f}")
        self.lbl_lfe_gain.setFixedWidth(35)
        self.lbl_lfe_gain.setStyleSheet("color: #f5a623; font-family: Consolas;")
        lfe_layout.addWidget(self.lbl_lfe_gain, 2, 2)
        main_layout.addWidget(lfe_group)

        # ── Options stéréo ────────────────────────────────────────────
        stereo_group = QGroupBox("OPTIONS STÉRÉO")
        stereo_layout = QVBoxLayout(stereo_group)
        stereo_layout.setSpacing(8)

        sep_row = QHBoxLayout()
        sep_row.addWidget(QLabel("Séparation stéréo :"))
        self.sld_stereo_sep = QSlider(Qt.Orientation.Horizontal)
        self.sld_stereo_sep.setRange(0, 100)
        self.sld_stereo_sep.setValue(int(self.config.stereo_separation * 100))
        sep_row.addWidget(self.sld_stereo_sep)
        self.lbl_stereo_sep = QLabel(f"{int(self.config.stereo_separation * 180)}°")
        self.lbl_stereo_sep.setFixedWidth(36)
        self.lbl_stereo_sep.setStyleSheet("color: #f5a623; font-family: Consolas;")
        sep_row.addWidget(self.lbl_stereo_sep)
        stereo_layout.addLayout(sep_row)

        hint = QLabel("0° = mono   ·   180° = stéréo complet")
        self._stereo_hint = hint
        hint.setStyleSheet("font-size: 10px; color: #5a4a28;")
        stereo_layout.addWidget(hint)

        self.chk_mono = QCheckBox("Mixer en mono  (L+R)/2")
        self.chk_mono.setChecked(self.config.mix_mono)
        stereo_layout.addWidget(self.chk_mono)

        self.chk_invert = QCheckBox("Inverser stéréo  (L ↔ R)")
        self.chk_invert.setChecked(self.config.invert_stereo)
        stereo_layout.addWidget(self.chk_invert)
        main_layout.addWidget(stereo_group)

        main_layout.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def set_theme_colors(self, colors: dict):
        accent = colors.get("accent", "#f5a623")
        muted = colors.get("text_muted", "#5a4a28")
        border = colors.get("border_bright", "#3d3420")
        secondary = colors.get("text_secondary", "#a08060")
        for label in (self.lbl_blend, self.lbl_phase, self.lbl_lfe_gain, self.lbl_stereo_sep):
            label.setStyleSheet(f"color: {accent}; font-family: Consolas;")
        self._lbl_front.setStyleSheet(f"color: {muted}; font-size: 10px; letter-spacing: 3px;")
        self._lbl_surr.setStyleSheet(f"color: {muted}; font-size: 10px; letter-spacing: 3px; margin-top: 4px;")
        self._legend.setStyleSheet(f"font-size: 10px; color: {border};")
        self._stereo_hint.setStyleSheet(f"font-size: 10px; color: {muted};")

    def _connect_signals(self):
        self.ch_fl.value_changed.connect(lambda v: self._update("gain_fl", v))
        self.ch_fr.value_changed.connect(lambda v: self._update("gain_fr", v))
        self.ch_c.value_changed.connect(lambda v: self._update("gain_c", v))
        self.ch_lfe.value_changed.connect(lambda v: self._update("gain_lfe", v))
        self.ch_sl.value_changed.connect(lambda v: self._update("gain_sl", v))
        self.ch_sr.value_changed.connect(lambda v: self._update("gain_sr", v))

        self.chk_double.toggled.connect(self._on_double_toggled)
        self.sld_blend.valueChanged.connect(self._on_blend_changed)
        self.chk_phase.toggled.connect(self._on_phase_toggled)
        self.sld_phase.valueChanged.connect(self._on_phase_changed)

        self.chk_lfe.toggled.connect(self._on_lfe_toggled)
        self.spin_lpf.valueChanged.connect(self._on_lpf_changed)
        self.sld_lfe_gain.valueChanged.connect(self._on_lfe_gain_changed)

        self.sld_stereo_sep.valueChanged.connect(self._on_stereo_sep_changed)
        self.chk_mono.toggled.connect(self._on_mono_toggled)
        self.chk_invert.toggled.connect(self._on_invert_toggled)

    def _update(self, attr, value):
        setattr(self.config, attr, value)
        self.config_changed.emit(self.config)

    def _on_double_toggled(self, checked):
        self.config.double_front_to_surround = checked
        self.sld_blend.setEnabled(checked)
        self.config_changed.emit(self.config)

    def _on_blend_changed(self, v):
        val = v / 100.0
        self.lbl_blend.setText(f"{val:.0%}")
        self.config.surround_blend = val
        self.config_changed.emit(self.config)

    def _on_phase_toggled(self, checked):
        self.config.phase_to_surround = checked
        self.sld_phase.setEnabled(checked)
        self.config_changed.emit(self.config)

    def _on_phase_changed(self, v):
        val = v / 100.0
        self.lbl_phase.setText(f"{val:.0%}")
        self.config.phase_rear_blend = val
        self.config_changed.emit(self.config)

    def _on_lfe_toggled(self, checked):
        self.config.mix_to_lfe = checked
        self.spin_lpf.setEnabled(checked)
        self.sld_lfe_gain.setEnabled(checked)
        self.config_changed.emit(self.config)

    def _on_lpf_changed(self, v):
        self.config.lfe_low_pass_hz = v
        self.config_changed.emit(self.config)

    def _on_lfe_gain_changed(self, v):
        val = v / 100.0
        self.lbl_lfe_gain.setText(f"{val:.1f}")
        self.config.lfe_gain = val
        self.config_changed.emit(self.config)

    def _on_stereo_sep_changed(self, v):
        val = v / 100.0
        self.lbl_stereo_sep.setText(f"{int(val * 180)}°")
        self.config.stereo_separation = val
        if self.config.mix_mono:
            self.chk_mono.setChecked(False)
        self.config_changed.emit(self.config)

    def _on_mono_toggled(self, checked):
        self.config.mix_mono = checked
        self.sld_stereo_sep.setEnabled(not checked)
        self.config_changed.emit(self.config)

    def _on_invert_toggled(self, checked):
        self.config.invert_stereo = checked
        self.config_changed.emit(self.config)

    def apply_config(self, config: SpatialConfig):
        self.config = config
        self.ch_fl.set_value(config.gain_fl)
        self.ch_fr.set_value(config.gain_fr)
        self.ch_c.set_value(config.gain_c)
        self.ch_lfe.set_value(config.gain_lfe)
        self.ch_sl.set_value(config.gain_sl)
        self.ch_sr.set_value(config.gain_sr)
        self.chk_double.setChecked(config.double_front_to_surround)
        self.sld_blend.setValue(int(config.surround_blend * 100))
        self.chk_phase.setChecked(config.phase_to_surround)
        self.sld_phase.setValue(int(config.phase_rear_blend * 100))
        self.chk_lfe.setChecked(config.mix_to_lfe)
        self.spin_lpf.setValue(config.lfe_low_pass_hz)
        self.sld_lfe_gain.setValue(int(config.lfe_gain * 100))
        self.sld_stereo_sep.setValue(int(config.stereo_separation * 100))
        self.chk_mono.setChecked(config.mix_mono)
        self.chk_invert.setChecked(config.invert_stereo)
