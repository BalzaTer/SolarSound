"""
Tests unitaires simplifiés pour le shuffle intelligent (sans pytest).
"""

import sys
import random

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
from core.playlist import Playlist, PlayMode
from core.session import SessionState


def create_sample_tracks():
    """Crée des pistes de test."""
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
            duration=90.0,  # 1.5 minutes
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


def test_smart_shuffle_config():
    """Test SmartShuffleConfig."""
    print("Testing SmartShuffleConfig...")
    
    # Test default config
    config = SmartShuffleConfig.default()
    assert config.mode == ShuffleMode.SIMPLE
    assert config.bpm_weight == 50
    assert config.energy_weight == 30
    assert config.volume_weight == 20
    assert config.validate() is True
    
    # Test validation
    config.bpm_weight = 150
    assert config.validate() is False
    
    # Test serialization
    data = config.to_dict()
    new_config = SmartShuffleConfig.from_dict(data)
    assert new_config.mode == ShuffleMode.SIMPLE
    
    print("  ✓ SmartShuffleConfig tests passed")


def test_select_first_track():
    """Test select_first_track."""
    print("Testing select_first_track...")
    
    tracks = create_sample_tracks()
    
    # Test with min duration
    config = SmartShuffleConfig(
        mode=ShuffleMode.INTELLIGENT,
        first_track_min_duration=120.0,
        first_track_selection="random"
    )
    first_idx = select_first_track(tracks, config)
    assert first_idx in [0, 1, 3, 4]  # Tracks with duration >= 120
    
    # Test high energy selection
    config.first_track_selection = "high_energy"
    first_idx = select_first_track(tracks, config)
    assert first_idx in [0, 1, 3]  # Tracks with energy >= 0.7
    
    print("  ✓ select_first_track tests passed")


def test_compatibility_score():
    """Test compatibility_score."""
    print("Testing compatibility_score...")
    
    tracks = create_sample_tracks()
    
    # Test BPM proximity
    config = SmartShuffleConfig(
        mode=ShuffleMode.INTELLIGENT,
        bpm_weight=100,
        energy_weight=0,
        volume_weight=0,
        bpm_tolerance=5.0
    )
    score = compatibility_score(tracks[0], tracks[1], config)
    assert score == 100.0
    
    # Test BPM multiples
    config.enable_bpm_multiples = True
    score = compatibility_score(tracks[0], tracks[3], config)  # 120 vs 180
    assert score >= 85.0
    
    # Test energy compatibility
    config = SmartShuffleConfig(
        mode=ShuffleMode.INTELLIGENT,
        bpm_weight=0,
        energy_weight=100,
        volume_weight=0,
        energy_tolerance=0.1
    )
    score = compatibility_score(tracks[0], tracks[1], config)
    assert score == 100.0
    
    print("  ✓ compatibility_score tests passed")


def test_build_smart_shuffle():
    """Test build_smart_shuffle."""
    print("Testing build_smart_shuffle...")
    
    tracks = create_sample_tracks()
    config = SmartShuffleConfig(
        mode=ShuffleMode.INTELLIGENT,
        first_track_min_duration=0
    )
    
    order = build_smart_shuffle(tracks, config)
    assert len(order) == len(tracks)
    assert set(order) == set(range(len(tracks)))
    
    # Test first track duration
    config.first_track_min_duration = 120.0
    order = build_smart_shuffle(tracks, config)
    first_track = tracks[order[0]]
    assert first_track.duration >= 120.0
    
    print("  ✓ build_smart_shuffle tests passed")


def test_select_next_track_with_randomness():
    """Test select_next_track_with_randomness."""
    print("Testing select_next_track_with_randomness...")
    
    config = SmartShuffleConfig(
        mode=ShuffleMode.INTELLIGENT,
        randomness_factor=0.0
    )
    candidates = [(0, 90.0), (1, 80.0), (2, 70.0)]
    idx = select_next_track_with_randomness(candidates, config)
    assert idx == 0
    
    config.randomness_factor = 1.0
    idx = select_next_track_with_randomness(candidates, config)
    assert idx in [0, 1, 2]
    
    print("  ✓ select_next_track_with_randomness tests passed")


def test_playlist_integration():
    """Test Playlist integration."""
    print("Testing Playlist integration...")
    
    tracks = create_sample_tracks()
    config = SmartShuffleConfig(
        mode=ShuffleMode.INTELLIGENT,
        first_track_min_duration=0
    )
    
    playlist = Playlist()
    playlist.smart_shuffle_config = config
    playlist.play_mode = PlayMode.RANDOM
    
    for track in tracks:
        playlist.add_track(track)
    
    assert len(playlist.tracks) == len(tracks)
    assert playlist.smart_shuffle_config is not None
    
    print("  ✓ Playlist integration tests passed")


def test_session_integration():
    """Test SessionState integration."""
    print("Testing SessionState integration...")
    
    config = SmartShuffleConfig.default()
    config.mode = ShuffleMode.INTELLIGENT
    
    session = SessionState()
    session.smart_shuffle_config = config.to_dict()
    
    assert session.smart_shuffle_config is not None
    assert session.smart_shuffle_config["mode"] == "intelligent"
    
    print("  ✓ SessionState integration tests passed")


def test_smart_track():
    """Test SmartTrack."""
    print("Testing SmartTrack...")
    
    # Test creation
    track = SmartTrack(
        path="test.mp3",
        title="Test",
        duration=180.0,
        bpm=120.0,
        energy=0.8,
        start_energy=0.8,
        end_energy=0.7
    )
    assert track.path == "test.mp3"
    assert track.bpm == 120.0
    assert track.start_energy == 0.8
    
    # Test from_custom_track
    custom = CustomTrack(
        path="test.mp3",
        title="Test",
        duration=180.0,
        bpm=120.0,
        energy=0.8
    )
    smart = SmartTrack.from_custom_track(custom)
    assert smart.path == custom.path
    assert smart.bpm == custom.bpm
    assert smart.start_energy is None
    
    # Test serialization
    data = track.to_dict()
    assert data["path"] == "test.mp3"
    assert data["bpm"] == 120.0
    
    # Test deserialization
    new_track = SmartTrack.from_dict(data)
    assert new_track.path == track.path
    assert new_track.bpm == track.bpm
    
    print("  ✓ SmartTrack tests passed")


def test_utility_functions():
    """Test utility functions."""
    print("Testing utility functions...")
    
    tracks = create_sample_tracks()
    
    # Test get_track_bpm
    bpm = get_track_bpm(tracks[0])
    assert bpm == 120.0
    
    # Test get_track_energy
    energy = get_track_energy(tracks[0], "start")
    assert energy == 0.8
    energy = get_track_energy(tracks[0], "end")
    assert energy == 0.7
    
    # Test get_track_volume
    volume = get_track_volume(tracks[0], "start")
    assert volume == 0.7
    
    print("  ✓ Utility functions tests passed")


def run_all_tests():
    """Exécute tous les tests."""
    print("\n" + "="*60)
    print("Running Smart Shuffle Tests")
    print("="*60 + "\n")
    
    tests = [
        test_smart_shuffle_config,
        test_select_first_track,
        test_compatibility_score,
        test_build_smart_shuffle,
        test_select_next_track_with_randomness,
        test_playlist_integration,
        test_session_integration,
        test_smart_track,
        test_utility_functions,
    ]
    
    failed = []
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"  ✗ {test.__name__} FAILED: {e}")
            failed.append(test.__name__)
        except Exception as e:
            print(f"  ✗ {test.__name__} ERROR: {e}")
            failed.append(test.__name__)
    
    print("\n" + "="*60)
    if not failed:
        print("✓ All tests passed!")
        print("="*60)
        return 0
    else:
        print(f"✗ {len(failed)} test(s) failed:")
        for name in failed:
            print(f"  - {name}")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
