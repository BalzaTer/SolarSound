from core.custom_playlist import CustomPlaylist, CustomTrack
from core.playlist_manager import PlaylistManager


def test_favorites_playlist_is_created_toggled_and_persisted(tmp_path):
    manager = PlaylistManager(app_data_dir=str(tmp_path))
    track = CustomTrack(path=str(tmp_path / "song.mp3"), title="Song")

    assert manager.get_favorites_playlist() is None
    assert manager.set_track_favorite(track, True)

    favorites = manager.get_favorites_playlist()
    assert favorites is not None
    assert favorites.name == "Mes coups de coeur"
    assert favorites.is_favorites
    assert [saved_track.path for saved_track in favorites.tracks] == [track.path]
    assert manager.is_track_favorite(track.path)
    assert manager.set_track_favorite(track, True)
    assert len(favorites.tracks) == 1

    reloaded_manager = PlaylistManager(app_data_dir=str(tmp_path))
    assert reloaded_manager.load_all()
    reloaded = reloaded_manager.get_favorites_playlist()
    assert reloaded is not None
    assert reloaded.is_favorites
    assert reloaded_manager.is_track_favorite(track.path)
    assert reloaded_manager.set_track_favorite(track, False)
    assert not reloaded_manager.is_track_favorite(track.path)


def test_legacy_favorites_playlist_is_recognized_and_keeps_identity(tmp_path):
    manager = PlaylistManager(app_data_dir=str(tmp_path))
    legacy_playlist = CustomPlaylist(name="Mes coups de coeur")
    manager.library.add_playlist(legacy_playlist)
    assert manager.save_all()

    loaded_manager = PlaylistManager(app_data_dir=str(tmp_path))
    assert loaded_manager.load_all()
    favorites = loaded_manager.get_favorites_playlist()

    assert favorites is not None
    assert favorites.id == legacy_playlist.id
    assert favorites.is_favorites
    assert loaded_manager.update_playlist(favorites.id, name="Favoris")

    reloaded_manager = PlaylistManager(app_data_dir=str(tmp_path))
    assert reloaded_manager.load_all()
    renamed_favorites = reloaded_manager.get_favorites_playlist()
    assert renamed_favorites is not None
    assert renamed_favorites.name == "Favoris"
    assert renamed_favorites.is_favorites
