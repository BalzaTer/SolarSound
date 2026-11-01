import json
import os
import sys

import pytest

from core import app_paths
from core.error_logging import append_error_log
from core.playlist_manager import PlaylistManager
from core.session import SessionManager, SessionState


def _set_user_data_root(monkeypatch, path):
    if os.name == "nt":
        monkeypatch.setenv("APPDATA", str(path))
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
    elif sys.platform == "darwin":
        monkeypatch.setenv("HOME", str(path))
    else:
        monkeypatch.setenv("XDG_DATA_HOME", str(path))


def _set_legacy_dir(monkeypatch, path):
    legacy_dir = path / "legacy"
    legacy_dir.mkdir()
    monkeypatch.setattr(app_paths, "get_legacy_app_data_dir", lambda: str(legacy_dir))
    return legacy_dir


def test_app_data_dir_is_created_under_user_profile(tmp_path, monkeypatch):
    user_root = tmp_path / "profile-data"
    _set_user_data_root(monkeypatch, user_root)

    app_data_dir = app_paths.get_app_data_dir()

    if os.name == "nt":
        expected_dir = user_root / "SolarSound"
    elif sys.platform == "darwin":
        expected_dir = user_root / "Library" / "Application Support" / "SolarSound"
    else:
        expected_dir = user_root / "SolarSound"
    assert app_data_dir == str(expected_dir)
    assert os.path.isdir(app_data_dir)


def test_migration_copies_existing_file_without_overwriting(tmp_path, monkeypatch):
    legacy_dir = tmp_path / "legacy"
    app_data_dir = tmp_path / "user-data"
    legacy_dir.mkdir()
    app_data_dir.mkdir()
    (legacy_dir / "settings.json").write_text('{"legacy": true}', encoding="utf-8")
    (app_data_dir / "settings.json").write_text('{"current": true}', encoding="utf-8")
    monkeypatch.setattr(app_paths, "get_legacy_app_data_dir", lambda: str(legacy_dir))

    app_paths.migrate_legacy_file("settings.json", str(app_data_dir))

    assert (app_data_dir / "settings.json").read_text(encoding="utf-8") == '{"current": true}'


def test_session_and_playlist_json_use_user_data_dir(tmp_path, monkeypatch):
    user_root = tmp_path / "profile-data"
    _set_user_data_root(monkeypatch, user_root)
    _set_legacy_dir(monkeypatch, tmp_path)

    session = SessionManager()
    session.save(SessionState())
    playlists = PlaylistManager()
    assert playlists.save_all()

    expected_dir = user_root / "SolarSound"
    assert (expected_dir / "solarsound_session.json").is_file()
    assert (expected_dir / "solarsound_playlists.json").is_file()


def test_default_error_log_uses_user_data_dir(tmp_path, monkeypatch):
    user_root = tmp_path / "profile-data"
    _set_user_data_root(monkeypatch, user_root)
    legacy_working_dir = tmp_path / "working-directory"
    legacy_working_dir.mkdir()
    monkeypatch.chdir(legacy_working_dir)
    old_entry = {"message": "legacy log entry"}
    (legacy_working_dir / "playback_errors.log").write_text(
        json.dumps(old_entry) + "\n", encoding="utf-8"
    )

    log_path = append_error_log("test", "")

    assert log_path == os.path.join(str(user_root), "SolarSound", "playback_errors.log")
    with open(log_path, "r", encoding="utf-8") as log_file:
        assert json.loads(log_file.readline()) == old_entry
        assert json.loads(log_file.readline())["message"] == "test"


def test_legacy_covers_are_migrated_without_overwriting(tmp_path, monkeypatch):
    legacy_dir = tmp_path / "legacy"
    app_data_dir = tmp_path / "user-data"
    legacy_covers = legacy_dir / "playlist_covers"
    legacy_covers.mkdir(parents=True)
    (legacy_covers / "cover.jpg").write_bytes(b"legacy cover")
    current_cover = app_data_dir / "playlist_covers" / "cover.jpg"
    current_cover.parent.mkdir(parents=True)
    current_cover.write_bytes(b"current cover")
    monkeypatch.setattr(app_paths, "get_legacy_app_data_dir", lambda: str(legacy_dir))

    app_paths.migrate_legacy_directory("playlist_covers", str(app_data_dir))

    assert current_cover.read_bytes() == b"current cover"


@pytest.mark.parametrize("filename", ["solarsound_session.json", "solarsound_playlists.json"])
def test_legacy_json_is_migrated_to_user_data(tmp_path, monkeypatch, filename):
    legacy_dir = tmp_path / "legacy"
    user_root = tmp_path / "profile-data"
    legacy_dir.mkdir()
    (legacy_dir / filename).write_text('{"migrated": true}', encoding="utf-8")
    _set_user_data_root(monkeypatch, user_root)
    monkeypatch.setattr(app_paths, "get_legacy_app_data_dir", lambda: str(legacy_dir))

    if filename == "solarsound_session.json":
        SessionManager()
    else:
        PlaylistManager()

    migrated_file = user_root / "SolarSound" / filename
    assert json.loads(migrated_file.read_text(encoding="utf-8")) == {"migrated": True}
