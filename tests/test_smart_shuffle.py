"""
Tests unitaires pour le shuffle intelligent.
"""

import pytest
import random
from unittest.mock import MagicMock, patch

# Importer les modules
from core.smart_shuffle_config import SmartShuffleConfig, ShuffleMode
from core.smart_shuffle import (
    select_first_track,
    compatibility_score,
    build_smart_shuffle,
    select_next_track_with_randomness,
    get_track_bpm,
    get_track_energy,
    get_track_volume,
)
from core.custom_playlist import CustomTrack, SmartTrack


# --- Fixtures ---

@pytest.fixture
def sample_tracks():
    """Crée des pistes de test avec des BPM et énergies variés."""
    return [
        SmartTrack(
            path="track1.mp3",
            title="Track 1",
            duration=180.0,  # 3 minutes
            bpm=120.0,
            energy=0.8,
            start_energy=0.8,
            end_energy=0.7,
            start_volume=0.7,
            end_volume=0.6
        ),
        SmartTrack(
            path="track2.mp3",
            title="Track 2",
            duration=240.0,  # 4 minutes
            bpm=125.0,
            energy=0.7,
            start_energy=0.7,
            end_energy=0.6,
            start_volume=0.6,
            end_volume=0.5
        ),
        SmartTrack(
            path="track3.mp3",
            title="Track 3",
            duration=90.0,  # 1.5 minutes (trop court pour first_track_min_duration=30)
            bpm=60.0,
            energy=0.3,
            start_energy=0.3,
            end_energy=0.4,
            start_volume=0.4,
            end_volume=0.5
        ),
        SmartTrack(
            path="track4.mp3",
            title="Track 4",
            duration=300.0,  # 5 minutes
            bpm=180.0,
            energy=0.9,
            start_energy=0.9,
            end_energy=0.8,
            start_volume=0.8,
            end_volume=0.7
        ),
        SmartTrack(
            path="track5.mp3",
            title="Track 5",
            duration=150.0,  # 2.5 minutes
            bpm=90.0,
            energy=0.5,
            start_energy=0.5,
            end_energy=0.5,
            start_volume=0.5,
            end_volume=0.5
        ),
    ]


@pytest.fixture
def default_config():
    """Retourne la configuration par défaut."""
    return SmartShuffleConfig.default()


@pytest.fixture
def intelligent_config():
    """Retourne une configuration en mode intelligent."""
    config = SmartShuffleConfig.default()
    config.mode = ShuffleMode.INTELLIGENT
    return config


# --- Tests pour SmartShuffleConfig ---

class TestSmartShuffleConfig:
    """Tests pour la classe SmartShuffleConfig."""

    def test_default_config(self):
        """Teste la configuration par défaut."""
        config = SmartShuffleConfig.default()
        assert config.mode == ShuffleMode.SIMPLE
        assert config.bpm_weight == 50
        assert config.energy_weight == 30
        assert config.volume_weight == 20
        assert config.bpm_tolerance == 5.0
        assert config.enable_bpm_multiples is True
        assert config.first_track_min_duration == 30.0
        assert config.randomness_factor == 0.3

    def test_validate_valid(self):
        """Teste la validation avec une config valide."""
        config = SmartShuffleConfig.default()
        assert config.validate() is True

    def test_validate_invalid_weights(self):
        """Teste la validation avec des poids invalides."""
        config = SmartShuffleConfig.default()
        config.bpm_weight = 150  # > 100
        assert config.validate() is False

    def test_validate_weights_sum(self):
        """Teste la validation avec une somme de poids != 100."""
        config = SmartShuffleConfig.default()
        config.bpm_weight = 60
        config.energy_weight = 30
        config.volume_weight = 30  # 60+30+30=120
        assert config.validate() is False

    def test_to_dict_and_from_dict(self):
        """Teste la sérialisation et désérialisation."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            bpm_weight=60,
            energy_weight=25,
            volume_weight=15,
            bpm_tolerance=10.0,
            first_track_min_duration=45.0
        )
        data = config.to_dict()
        new_config = SmartShuffleConfig.from_dict(data)
        assert new_config.mode == ShuffleMode.INTELLIGENT
        assert new_config.bpm_weight == 60
        assert new_config.energy_weight == 25
        assert new_config.volume_weight == 15
        assert new_config.bpm_tolerance == 10.0
        assert new_config.first_track_min_duration == 45.0


# --- Tests pour select_first_track ---

class TestSelectFirstTrack:
    """Tests pour la fonction select_first_track."""

    def test_random_selection(self, sample_tracks):
        """Teste la sélection aléatoire."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            first_track_min_duration=0,  # Accepte toutes les pistes
            first_track_selection="random"
        )
        with patch('random.choice') as mock_choice:
            mock_choice.return_value = (1, sample_tracks[1])
            idx = select_first_track(sample_tracks, config)
            assert idx == 1

    def test_high_energy_selection(self, sample_tracks):
        """Teste la sélection par énergie élevée."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            first_track_min_duration=0,
            first_track_selection="high_energy"
        )
        # Track 4 a energy=0.9 (la plus élevée)
        idx = select_first_track(sample_tracks, config)
        assert idx in [0, 1, 3]  # Tracks avec energy >= 0.7

    def test_low_energy_selection(self, sample_tracks):
        """Teste la sélection par énergie faible."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            first_track_min_duration=0,
            first_track_selection="low_energy"
        )
        # Track 2 a energy=0.3 (la plus faible)
        idx = select_first_track(sample_tracks, config)
        assert idx in [2]  # Seule piste avec energy <= 0.3

    def test_balanced_selection(self, sample_tracks):
        """Teste la sélection équilibrée."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            first_track_min_duration=0,
            first_track_selection="balanced"
        )
        idx = select_first_track(sample_tracks, config)
        assert 0 <= idx < len(sample_tracks)

    def test_min_duration_filter(self, sample_tracks):
        """Teste le filtrage par durée minimale."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            first_track_min_duration=120.0,  # 2 minutes
            first_track_selection="random"
        )
        # Seules les pistes 0, 1, 3, 4 ont duration >= 120
        idx = select_first_track(sample_tracks, config)
        assert idx in [0, 1, 3, 4]

    def test_empty_tracks(self):
        """Teste avec une liste vide."""
        config = SmartShuffleConfig.default()
        idx = select_first_track([], config)
        assert idx == -1


# --- Tests pour compatibility_score ---

class TestCompatibilityScore:
    """Tests pour la fonction compatibility_score."""

    def test_bpm_proche(self, sample_tracks):
        """Teste la compatibilité BPM proches."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            bpm_weight=100,
            energy_weight=0,
            volume_weight=0,
            bpm_tolerance=5.0
        )
        # Track 0: BPM=120, Track 1: BPM=125 (diff=5, dans la tolérance)
        score = compatibility_score(sample_tracks[0], sample_tracks[1], config)
        assert score == 100.0

    def test_bpm_multiples(self, sample_tracks):
        """Teste la compatibilité BPM multiples."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            bpm_weight=100,
            energy_weight=0,
            volume_weight=0,
            enable_bpm_multiples=True,
            bpm_multiple_ratio_tolerance=0.1
        )
        # Track 0: BPM=120, Track 3: BPM=180 (ratio=1.5)
        score = compatibility_score(sample_tracks[0], sample_tracks[3], config)
        assert score >= 85.0  # Doit être élevé pour les multiples

    def test_energy_compatible(self, sample_tracks):
        """Teste la compatibilité énergie."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            bpm_weight=0,
            energy_weight=100,
            volume_weight=0,
            energy_tolerance=0.1
        )
        # Track 0: end_energy=0.7, Track 1: start_energy=0.7 (diff=0)
        score = compatibility_score(sample_tracks[0], sample_tracks[1], config)
        assert score == 100.0

    def test_volume_compatible(self, sample_tracks):
        """Teste la compatibilité volume."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            bpm_weight=0,
            energy_weight=0,
            volume_weight=100,
            volume_tolerance=0.1
        )
        # Track 0: end_volume=0.6, Track 1: start_volume=0.6 (diff=0)
        score = compatibility_score(sample_tracks[0], sample_tracks[1], config)
        assert score == 100.0

    def test_mixed_weights(self, sample_tracks):
        """Teste avec des poids mélangés."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            bpm_weight=50,
            energy_weight=30,
            volume_weight=20
        )
        # Track 0 → Track 1: BPM proche, énergie compatible, volume compatible
        score = compatibility_score(sample_tracks[0], sample_tracks[1], config)
        assert 80 <= score <= 100


# --- Tests pour build_smart_shuffle ---

class TestBuildSmartShuffle:
    """Tests pour la fonction build_smart_shuffle."""

    def test_all_tracks_included(self, sample_tracks):
        """Teste que toutes les pistes sont incluses."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            first_track_min_duration=0
        )
        order = build_smart_shuffle(sample_tracks, config)
        assert len(order) == len(sample_tracks)
        assert set(order) == set(range(len(sample_tracks)))

    def test_first_track_duration(self, sample_tracks):
        """Teste que le premier morceau respecte la durée minimale."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            first_track_min_duration=120.0
        )
        order = build_smart_shuffle(sample_tracks, config)
        first_idx = order[0]
        first_track = sample_tracks[first_idx]
        assert first_track.duration >= 120.0

    def test_empty_list(self):
        """Teste avec une liste vide."""
        config = SmartShuffleConfig.default()
        order = build_smart_shuffle([], config)
        assert order == []

    def test_single_track(self, sample_tracks):
        """Teste avec une seule piste."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            first_track_min_duration=0
        )
        order = build_smart_shuffle([sample_tracks[0]], config)
        assert order == [0]


# --- Tests pour select_next_track_with_randomness ---

class TestSelectNextTrackWithRandomness:
    """Tests pour la fonction select_next_track_with_randomness."""

    def test_deterministic_mode(self):
        """Teste le mode déterministe (randomness_factor=0)."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            randomness_factor=0.0
        )
        candidates = [(0, 90.0), (1, 80.0), (2, 70.0)]
        idx = select_next_track_with_randomness(candidates, config)
        assert idx == 0  # Doit choisir le meilleur score

    def test_random_mode(self):
        """Teste le mode aléatoire pur (randomness_factor=1)."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            randomness_factor=1.0
        )
        candidates = [(0, 90.0), (1, 80.0), (2, 70.0)]
        # En mode aléatoire pur, n'importe quel index peut être choisi
        idx = select_next_track_with_randomness(candidates, config)
        assert idx in [0, 1, 2]

    def test_mixed_mode(self):
        """Teste le mode mixte."""
        config = SmartShuffleConfig(
            mode=ShuffleMode.INTELLIGENT,
            randomness_factor=0.5
        )
        candidates = [(0, 90.0), (1, 80.0), (2, 70.0)]
        idx = select_next_track_with_randomness(candidates, config)
        assert idx in [0, 1, 2]

    def test_empty_candidates(self):
        """Teste avec une liste vide de candidats."""
        config = SmartShuffleConfig.default()
        idx = select_next_track_with_randomness([], config)
        assert idx == -1


# --- Tests pour les fonctions utilitaires ---

class TestUtilityFunctions:
    """Tests pour les fonctions utilitaires."""

    def test_get_track_bpm(self, sample_tracks):
        """Teste la récupération du BPM."""
        bpm = get_track_bpm(sample_tracks[0])
        assert bpm == 120.0

    def test_get_track_bpm_none(self):
        """Teste la récupération du BPM avec None."""
        track = CustomTrack(path="test.mp3")
        bpm = get_track_bpm(track)
        assert bpm is None

    def test_get_track_energy(self, sample_tracks):
        """Teste la récupération de l'énergie."""
        energy = get_track_energy(sample_tracks[0], "start")
        assert energy == 0.8
        energy = get_track_energy(sample_tracks[0], "end")
        assert energy == 0.7
        energy = get_track_energy(sample_tracks[0], "avg")
        assert energy == 0.8

    def test_get_track_volume(self, sample_tracks):
        """Teste la récupération du volume."""
        volume = get_track_volume(sample_tracks[0], "start")
        assert volume == 0.7
        volume = get_track_volume(sample_tracks[0], "end")
        assert volume == 0.6


# --- Tests pour SmartTrack ---

class TestSmartTrack:
    """Tests pour la classe SmartTrack."""

    def test_creation(self):
        """Teste la création d'un SmartTrack."""
        track = SmartTrack(
            path="test.mp3",
            title="Test",
            duration=180.0,
            bpm=120.0,
            energy=0.8,
            start_energy=0.8,
            end_energy=0.7,
            start_volume=0.7,
            end_volume=0.6
        )
        assert track.path == "test.mp3"
        assert track.title == "Test"
        assert track.bpm == 120.0
        assert track.start_energy == 0.8
        assert track.end_energy == 0.7

    def test_from_custom_track(self):
        """Teste la conversion depuis CustomTrack."""
        custom = CustomTrack(
            path="test.mp3",
            title="Test",
            duration=180.0,
            bpm=120.0,
            energy=0.8
        )
        smart = SmartTrack.from_custom_track(custom)
        assert smart.path == custom.path
        assert smart.title == custom.title
        assert smart.bpm == custom.bpm
        assert smart.energy == custom.energy
        assert smart.start_energy is None
        assert smart.end_energy is None

    def test_to_dict(self):
        """Teste la sérialisation."""
        track = SmartTrack(
            path="test.mp3",
            title="Test",
            bpm=120.0,
            start_energy=0.8
        )
        data = track.to_dict()
        assert data["path"] == "test.mp3"
        assert data["title"] == "Test"
        assert data["bpm"] == 120.0
        assert data["start_energy"] == 0.8

    def test_from_dict(self):
        """Teste la désérialisation."""
        data = {
            "path": "test.mp3",
            "title": "Test",
            "bpm": 120.0,
            "start_energy": 0.8
        }
        track = SmartTrack.from_dict(data)
        assert track.path == "test.mp3"
        assert track.title == "Test"
        assert track.bpm == 120.0
        assert track.start_energy == 0.8


# --- Tests pour ShuffleMode ---

class TestShuffleMode:
    """Tests pour l'énumération ShuffleMode."""

    def test_values(self):
        """Teste les valeurs de ShuffleMode."""
        assert ShuffleMode.SIMPLE.value == "simple"
        assert ShuffleMode.INTELLIGENT.value == "intelligent"

    def test_from_string(self):
        """Teste la création depuis une chaîne."""
        assert ShuffleMode("simple") == ShuffleMode.SIMPLE
        assert ShuffleMode("intelligent") == ShuffleMode.INTELLIGENT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
