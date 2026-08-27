from audio.cd import make_cd_uri, parse_cd_uri


def test_cd_uri_round_trip():
    uri = make_cd_uri("d:", 3)

    assert uri == "cdda:///D:/track/3"
    assert parse_cd_uri(uri) == ("D:", 3)


def test_parse_cd_uri_rejects_regular_files():
    assert parse_cd_uri("C:/Music/song.mp3") is None