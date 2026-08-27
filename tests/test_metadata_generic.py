from audio import metadata


def test_read_metadata_uses_mutagen_for_other_audio_formats(monkeypatch, tmp_path):
    audio_path = tmp_path / "song.flac"
    audio_path.write_bytes(b"placeholder")

    class FakeAudio:
        info = type("Info", (), {"length": 12.5})()

        def get(self, key):
            return {"title": ["Titre"], "artist": ["Artiste"], "album": ["Album"]}.get(key)

    monkeypatch.setattr(metadata, "MUTAGEN_OK", True)
    monkeypatch.setattr(metadata, "MutagenFile", lambda path, easy: FakeAudio())

    result = metadata.read_metadata(str(audio_path))

    assert result == {
        "title": "Titre",
        "artist": "Artiste",
        "album": "Album",
        "duration": 12.5,
    }