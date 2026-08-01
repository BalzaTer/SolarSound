import math
import unittest

from core.volume import gain_to_slider_value, slider_to_gain


class VolumeMappingTests(unittest.TestCase):
    def test_slider_value_uses_logarithmic_mapping(self):
        gain = slider_to_gain(75)
        self.assertAlmostEqual(gain, 10 ** (-30 / 20), places=6)

    def test_three_decibels_increase(self):
        gain0 = slider_to_gain(75)
        gain3 = slider_to_gain(82)
        self.assertGreater(gain3, gain0)
        self.assertAlmostEqual(gain3 / gain0, 2.630267991895379, places=6)

    def test_gain_to_slider_value_round_trips(self):
        slider_value = gain_to_slider_value(0.5)
        self.assertGreaterEqual(slider_value, 0)
        self.assertLessEqual(slider_value, 150)
        self.assertAlmostEqual(slider_to_gain(slider_value), 0.5, delta=0.03)

    def test_boosted_volume_up_to_150_percent(self):
        gain = slider_to_gain(150)
        self.assertAlmostEqual(gain, 1.5, places=6)
        self.assertEqual(gain_to_slider_value(1.5), 150)


if __name__ == "__main__":
    unittest.main()
