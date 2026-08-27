from audio.metadata import read_cover_art_data


def test_read_cover_art_data_uses_local_cover_image(tmp_path):
    artwork_path = tmp_path / "cover.jpg"
    payload = b"\xff\xd8\xff"
    artwork_path.write_bytes(payload)

    audio_path = tmp_path / "song.mp3"
    audio_path.write_bytes(b"not-a-real-mp3")

    assert read_cover_art_data(str(audio_path)) == payload
