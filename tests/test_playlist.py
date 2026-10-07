import unittest

from core.playlist import PlayMode, Playlist, Track


class PlaylistShuffleTests(unittest.TestCase):
    def test_adding_tracks_after_current_track_at_end_of_shuffle(self):
        playlist = Playlist()
        playlist.play_mode = PlayMode.RANDOM
        playlist.add_track_batch([Track(path=f"{index}.mp3") for index in range(2)])
        playlist._shuffle_pos = len(playlist._shuffle_order) - 1
        playlist.current_index = playlist._shuffle_order[-1]

        added = playlist.add_track_batch(
            [Track(path=f"{index}.mp3") for index in range(2, 7)]
        )

        self.assertEqual(added, 5)
        self.assertEqual(sorted(playlist._shuffle_order), list(range(7)))

    def test_repeated_single_track_additions_keep_shuffle_indices_valid(self):
        playlist = Playlist()
        playlist.play_mode = PlayMode.RANDOM
        playlist.add_track_batch([Track(path="first.mp3")])
        playlist.set_current(0)

        for index in range(1, 8):
            playlist.add_track(Track(path=f"{index}.mp3"))

        self.assertEqual(sorted(playlist._shuffle_order), list(range(8)))


if __name__ == "__main__":
    unittest.main()
