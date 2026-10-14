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


class PlaylistIndependentLoopTests(unittest.TestCase):
    def make_random_playlist(self):
        playlist = Playlist()
        playlist.add_track_batch([Track(path=f"{index}.mp3") for index in range(3)])
        playlist.play_mode = PlayMode.RANDOM
        playlist._shuffle_order = [0, 1, 2]
        playlist._shuffle_pos = -1
        return playlist

    def test_random_order_without_loop_stops_at_end(self):
        playlist = self.make_random_playlist()

        self.assertEqual(playlist.next_track().path, "0.mp3")
        self.assertEqual(playlist.next_track().path, "1.mp3")
        self.assertEqual(playlist.next_track().path, "2.mp3")
        self.assertIsNone(playlist.next_track())

    def test_random_order_with_loop_all_wraps(self):
        playlist = self.make_random_playlist()
        playlist.loop_mode = PlayMode.LOOP_ALL

        for expected in ("0.mp3", "1.mp3", "2.mp3", "0.mp3"):
            self.assertEqual(playlist.next_track().path, expected)

    def test_random_order_with_loop_one_repeats_current_track(self):
        playlist = self.make_random_playlist()
        playlist.loop_mode = PlayMode.LOOP_ONE
        playlist.set_current(1)

        self.assertEqual(playlist.next_track().path, "1.mp3")
        self.assertEqual(playlist.prev_track().path, "1.mp3")


if __name__ == "__main__":
    unittest.main()
