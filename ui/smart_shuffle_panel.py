"""
Panneau de configuration du shuffle intelligent.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QSlider,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

try:
    from ..core.smart_shuffle_config import SmartShuffleConfig, ShuffleMode
    SMART_IMPORT_OK = True
except (ImportError, ModuleNotFoundError):
    SMART_IMPORT_OK = False


class SmartShufflePanel(QWidget):
    """
    Panneau de configuration pour le shuffle intelligent.
    """
    
    config_changed = pyqtSignal(SmartShuffleConfig)
    
    def __init__(self, config: SmartShuffleConfig = None, parent=None):
        super().__init__(parent)
        self._config = config or SmartShuffleConfig.default()
        self._initial_config = SmartShuffleConfig.from_dict(self._config.to_dict())
        self._setup_ui()
        self._update_from_config()
    
    def _setup_ui(self):
        """Initialise l'interface utilisateur."""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Titre
        title = QLabel("🎲 Mode Aléatoire Intelligent")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "Ce mode optimise les transitions entre les morceaux en tenant compte "
            "du BPM, de l'énergie et du volume."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666;")
        layout.addWidget(desc)
        
        # --- Mode principal ---
        mode_group = QGroupBox("Mode de Lecture")
        mode_layout = QHBoxLayout()
        
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Simple (aléatoire classique)", ShuffleMode.SIMPLE)
        self.cmb_mode.addItem("Intelligent (transitions optimisées)", ShuffleMode.INTELLIGENT)
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.cmb_mode)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # --- Paramètres du mode Intelligent ---
        self.smart_group = QGroupBox("Paramètres du Mode Intelligent")
        smart_layout = QVBoxLayout()
        smart_layout.setSpacing(10)
        
        # Poids des critères
        weights_group = QGroupBox("Importance des Critères")
        weights_layout = QVBoxLayout()
        
        # BPM Weight
        bpm_layout = QHBoxLayout()
        bpm_layout.addWidget(QLabel("BPM:"))
        self.slider_bpm_weight = QSlider(Qt.Orientation.Horizontal)
        self.slider_bpm_weight.setRange(0, 100)
        self.slider_bpm_weight.valueChanged.connect(self._on_weight_changed)
        self.lbl_bpm_weight = QLabel("50%")
        self.lbl_bpm_weight.setFixedWidth(40)
        self.lbl_bpm_weight.setAlignment(Qt.AlignmentFlag.AlignRight)
        bpm_layout.addWidget(self.slider_bpm_weight)
        bpm_layout.addWidget(self.lbl_bpm_weight)
        weights_layout.addLayout(bpm_layout)
        
        # Energy Weight
        energy_layout = QHBoxLayout()
        energy_layout.addWidget(QLabel("Énergie:"))
        self.slider_energy_weight = QSlider(Qt.Orientation.Horizontal)
        self.slider_energy_weight.setRange(0, 100)
        self.slider_energy_weight.valueChanged.connect(self._on_weight_changed)
        self.lbl_energy_weight = QLabel("30%")
        self.lbl_energy_weight.setFixedWidth(40)
        self.lbl_energy_weight.setAlignment(Qt.AlignmentFlag.AlignRight)
        energy_layout.addWidget(self.slider_energy_weight)
        energy_layout.addWidget(self.lbl_energy_weight)
        weights_layout.addLayout(energy_layout)
        
        # Volume Weight
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self.slider_volume_weight = QSlider(Qt.Orientation.Horizontal)
        self.slider_volume_weight.setRange(0, 100)
        self.slider_volume_weight.valueChanged.connect(self._on_weight_changed)
        self.lbl_volume_weight = QLabel("20%")
        self.lbl_volume_weight.setFixedWidth(40)
        self.lbl_volume_weight.setAlignment(Qt.AlignmentFlag.AlignRight)
        volume_layout.addWidget(self.slider_volume_weight)
        volume_layout.addWidget(self.lbl_volume_weight)
        weights_layout.addLayout(volume_layout)
        
        weights_group.setLayout(weights_layout)
        smart_layout.addWidget(weights_group)
        
        # Tolérances
        tolerances_group = QGroupBox("Tolérances")
        tolerances_layout = QVBoxLayout()
        
        # BPM Tolerance
        bpm_tol_layout = QHBoxLayout()
        bpm_tol_layout.addWidget(QLabel("BPM (±):"))
        self.spn_bpm_tolerance = QDoubleSpinBox()
        self.spn_bpm_tolerance.setRange(0.0, 50.0)
        self.spn_bpm_tolerance.setSingleStep(1.0)
        self.spn_bpm_tolerance.setSuffix(" BPM")
        self.spn_bpm_tolerance.valueChanged.connect(self._emit_config_changed)
        bpm_tol_layout.addWidget(self.spn_bpm_tolerance)
        tolerances_layout.addLayout(bpm_tol_layout)
        
        # Enable BPM Multiples
        self.chk_bpm_multiples = QCheckBox("Autoriser les multiples (ex: 80→160 BPM)")
        self.chk_bpm_multiples.setChecked(True)
        self.chk_bpm_multiples.stateChanged.connect(self._emit_config_changed)
        tolerances_layout.addWidget(self.chk_bpm_multiples)
        
        # Energy Tolerance
        energy_tol_layout = QHBoxLayout()
        energy_tol_layout.addWidget(QLabel("Énergie (±):"))
        self.spn_energy_tolerance = QDoubleSpinBox()
        self.spn_energy_tolerance.setRange(0.0, 1.0)
        self.spn_energy_tolerance.setSingleStep(0.05)
        self.spn_energy_tolerance.setSuffix("")
        self.spn_energy_tolerance.valueChanged.connect(self._emit_config_changed)
        energy_tol_layout.addWidget(self.spn_energy_tolerance)
        tolerances_layout.addLayout(energy_tol_layout)
        
        # Volume Tolerance
        volume_tol_layout = QHBoxLayout()
        volume_tol_layout.addWidget(QLabel("Volume (±):"))
        self.spn_volume_tolerance = QDoubleSpinBox()
        self.spn_volume_tolerance.setRange(0.0, 1.0)
        self.spn_volume_tolerance.setSingleStep(0.05)
        self.spn_volume_tolerance.setSuffix("")
        self.spn_volume_tolerance.valueChanged.connect(self._emit_config_changed)
        volume_tol_layout.addWidget(self.spn_volume_tolerance)
        tolerances_layout.addLayout(volume_tol_layout)
        
        tolerances_group.setLayout(tolerances_layout)
        smart_layout.addWidget(tolerances_group)
        
        # Sélection du premier morceau
        first_track_group = QGroupBox("Premier Morceau")
        first_track_layout = QVBoxLayout()
        
        # Min Duration
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Durée minimale:"))
        self.spn_first_track_duration = QSpinBox()
        self.spn_first_track_duration.setRange(0, 300)
        self.spn_first_track_duration.setSuffix(" secondes")
        self.spn_first_track_duration.valueChanged.connect(self._emit_config_changed)
        duration_layout.addWidget(self.spn_first_track_duration)
        first_track_layout.addLayout(duration_layout)
        
        # Selection Method
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("Méthode:"))
        self.cmb_first_track_selection = QComboBox()
        self.cmb_first_track_selection.addItems([
            "Aléatoire",
            "Énergie élevée",
            "Énergie faible",
            "Équilibré"
        ])
        self.cmb_first_track_selection.currentIndexChanged.connect(self._emit_config_changed)
        selection_layout.addWidget(self.cmb_first_track_selection)
        first_track_layout.addLayout(selection_layout)
        
        first_track_group.setLayout(first_track_layout)
        smart_layout.addWidget(first_track_group)
        
        # Aléatoire contrôlé
        randomness_group = QGroupBox("Aléatoire Contrôlé")
        randomness_layout = QVBoxLayout()
        
        randomness_hint = QLabel(
            "0% = déterministe (meilleures transitions seulement) \n"
            "100% = aléatoire pur (comme le mode Simple)"
        )
        randomness_hint.setWordWrap(True)
        randomness_hint.setStyleSheet("color: #666;")
        randomness_layout.addWidget(randomness_hint)
        
        randomness_slider_layout = QHBoxLayout()
        randomness_slider_layout.addWidget(QLabel("Niveau:"))
        self.slider_randomness = QSlider(Qt.Orientation.Horizontal)
        self.slider_randomness.setRange(0, 100)
        self.slider_randomness.valueChanged.connect(self._on_randomness_changed)
        self.lbl_randomness = QLabel("30%")
        self.lbl_randomness.setFixedWidth(40)
        self.lbl_randomness.setAlignment(Qt.AlignmentFlag.AlignRight)
        randomness_slider_layout.addWidget(self.slider_randomness)
        randomness_slider_layout.addWidget(self.lbl_randomness)
        randomness_layout.addLayout(randomness_slider_layout)
        
        randomness_group.setLayout(randomness_layout)
        smart_layout.addWidget(randomness_group)
        
        # Cache
        cache_layout = QHBoxLayout()
        self.chk_enable_cache = QCheckBox("Activer le cache des scores")
        self.chk_enable_cache.setChecked(True)
        self.chk_enable_cache.stateChanged.connect(self._emit_config_changed)
        cache_layout.addWidget(self.chk_enable_cache)
        cache_layout.addStretch()
        smart_layout.addLayout(cache_layout)
        
        self.smart_group.setLayout(smart_layout)
        layout.addWidget(self.smart_group)
        
        # Boutons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        btn_reset = QPushButton("Réinitialiser")
        btn_reset.clicked.connect(self._reset_to_defaults)
        buttons_layout.addWidget(btn_reset)
        
        btn_help = QPushButton("Aide")
        btn_help.clicked.connect(self._show_help)
        buttons_layout.addWidget(btn_help)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    def _update_from_config(self):
        """Met à jour l'UI depuis la configuration."""
        # Mode
        for i in range(self.cmb_mode.count()):
            if self.cmb_mode.itemData(i) == self._config.mode:
                self.cmb_mode.setCurrentIndex(i)
                break
        
        # Poids
        self.slider_bpm_weight.setValue(self._config.bpm_weight)
        self.slider_energy_weight.setValue(self._config.energy_weight)
        self.slider_volume_weight.setValue(self._config.volume_weight)
        self._update_weight_labels()
        
        # Tolérances
        self.spn_bpm_tolerance.setValue(self._config.bpm_tolerance)
        self.chk_bpm_multiples.setChecked(self._config.enable_bpm_multiples)
        self.spn_energy_tolerance.setValue(self._config.energy_tolerance)
        self.spn_volume_tolerance.setValue(self._config.volume_tolerance)
        
        # Premier morceau
        self.spn_first_track_duration.setValue(int(self._config.first_track_min_duration))
        selection_methods = ["random", "high_energy", "low_energy", "balanced"]
        for i, method in enumerate(selection_methods):
            if method == self._config.first_track_selection:
                self.cmb_first_track_selection.setCurrentIndex(i)
                break
        
        # Aléatoire
        self.slider_randomness.setValue(int(self._config.randomness_factor * 100))
        self._update_randomness_label()
        
        # Cache
        self.chk_enable_cache.setChecked(self._config.enable_cache)
        
        # Activer/désactiver les paramètres intelligents
        self._update_smart_params_enabled()
    
    def _on_mode_changed(self, index: int):
        """Gère le changement de mode."""
        mode_data = self.cmb_mode.itemData(index)
        if isinstance(mode_data, ShuffleMode):
            self._config.mode = mode_data
            self._update_smart_params_enabled()
            self._emit_config_changed()
    
    def _update_smart_params_enabled(self):
        """Active/désactive les paramètres selon le mode."""
        is_intelligent = self._config.mode == ShuffleMode.INTELLIGENT
        self.smart_group.setEnabled(is_intelligent)
    
    def _on_weight_changed(self):
        """Gère le changement des poids."""
        # Mettre à jour les valeurs
        self._config.bpm_weight = self.slider_bpm_weight.value()
        self._config.energy_weight = self.slider_energy_weight.value()
        self._config.volume_weight = self.slider_volume_weight.value()
        
        # Normaliser pour que la somme fasse 100
        total = self._config.bpm_weight + self._config.energy_weight + self._config.volume_weight
        if total > 0:
            # Ajuster automatiquement
            max_slider = max(
                self.slider_bpm_weight,
                self.slider_energy_weight,
                self.slider_volume_weight,
                key=lambda s: s.value()
            )
            if total != 100:
                max_slider.setValue(max_slider.value() + (100 - total))
                self._config.bpm_weight = self.slider_bpm_weight.value()
                self._config.energy_weight = self.slider_energy_weight.value()
                self._config.volume_weight = self.slider_volume_weight.value()
        
        self._update_weight_labels()
        self._emit_config_changed()
    
    def _update_weight_labels(self):
        """Met à jour les labels des poids."""
        self.lbl_bpm_weight.setText(f"{self.slider_bpm_weight.value()}%")
        self.lbl_energy_weight.setText(f"{self.slider_energy_weight.value()}%")
        self.lbl_volume_weight.setText(f"{self.slider_volume_weight.value()}%")
    
    def _on_randomness_changed(self):
        """Gère le changement du facteur d'aléatoire."""
        self._config.randomness_factor = self.slider_randomness.value() / 100.0
        self._update_randomness_label()
        self._emit_config_changed()
    
    def _update_randomness_label(self):
        """Met à jour le label du facteur d'aléatoire."""
        self.lbl_randomness.setText(f"{self.slider_randomness.value()}%")
    
    def _emit_config_changed(self):
        """Émet le signal de changement de configuration."""
        self.config_changed.emit(self._config)
    
    def _reset_to_defaults(self):
        """Réinitialise aux valeurs par défaut."""
        self._config = SmartShuffleConfig.default()
        self._update_from_config()
        self._emit_config_changed()
        QMessageBox.information(self, "Réinitialisé", "Les paramètres ont été réinitialisés aux valeurs par défaut.")
    
    def _show_help(self):
        """Affiche l'aide."""
        help_text = """
        <h2>Mode Aléatoire Intelligent</h2>
        <p>Ce mode optimise les transitions entre les morceaux en tenant compte :</p>
        <ul>
            <li><b>BPM</b> : Enchaîne les morceaux avec des tempos proches ou multiples (ex: 80 → 160).</li>
            <li><b>Énergie</b> : Favorise les transitions douces (ex: fin calme → début calme).</li>
            <li><b>Volume</b> : Prend en compte les fade-in/fade-out.</li>
        </ul>
        <p><b>Poids</b> : Contrôle l'importance relative de chaque critère (somme = 100%).</p>
        <p><b>Tolérances</b> : Définit la marge acceptable pour considérer deux valeurs comme proches.</p>
        <p><b>Aléatoire</b> : Contrôle le compromis entre optimisation et aléatoire.</p>
        <ul>
            <li>0% : Toujours choisir la meilleure transition (déterministe).</li>
            <li>50% : Équilibre entre optimisation et aléatoire.</li>
            <li>100% : Aléatoire pur (équivalent au mode Simple).</li>
        </ul>
        <p><b>Premier morceau</b> : Sélectionne un morceau de durée minimale pour initialiser les calculs.</p>
        """
        QMessageBox.information(self, "Aide - Shuffle Intelligent", help_text)
    
    def get_config(self) -> SmartShuffleConfig:
        """Retourne la configuration actuelle."""
        return self._config
    
    def set_config(self, config: SmartShuffleConfig):
        """Définit une nouvelle configuration."""
        self._config = config
        self._update_from_config()
    
    def can_apply(self) -> bool:
        """Vérifie si la configuration a été modifiée."""
        return self._config.to_dict() != self._initial_config.to_dict()
