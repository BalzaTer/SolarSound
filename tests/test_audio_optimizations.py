import unittest

import numpy as np

from audio.engine import AudioEngine, EqualizerConfig
from audio.vinyl import VinylConfig, VinylProcessor


def _scalar_equalize(chunk, frequencies, gains, sample_rate, states):
    output = chunk.astype(np.float64, copy=True)
    for index, (frequency, gain) in enumerate(zip(frequencies, gains)):
        if abs(gain) < 0.01:
            continue
        frequency = max(20.0, min(sample_rate * 0.45, float(frequency)))
        amplitude = 10.0 ** (float(gain) / 40.0)
        omega = 2.0 * np.pi * frequency / sample_rate
        alpha = np.sin(omega) / 2.0
        b0, b1, b2 = 1 + alpha * amplitude, -2 * np.cos(omega), 1 - alpha * amplitude
        a0, a1, a2 = 1 + alpha / amplitude, -2 * np.cos(omega), 1 - alpha / amplitude
        b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
        for channel in range(2):
            x1, x2, y1, y2 = states[index][channel]
            for sample in range(len(output)):
                x0 = output[sample, channel]
                y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
                output[sample, channel] = y0
                x2, x1, y2, y1 = x1, x0, y1, y0
            states[index][channel] = (x1, x2, y1, y2)
    return np.clip(output, -1.0, 1.0).astype(np.float32)


class AudioOptimizationTests(unittest.TestCase):
    def test_sos_equalizer_matches_previous_sample_by_sample_filter(self):
        engine = AudioEngine()
        engine._sample_rate = 44100
        frequencies = [80, 500, 3000, 12000]
        gains = [-6.0, 3.5, 8.0, -2.0]
        engine.equalizer_config = EqualizerConfig(
            frequencies=frequencies,
            gains=gains,
        )
        states = [np.zeros((2, 4), dtype=np.float64) for _ in frequencies]
        rng = np.random.default_rng(17)

        for block_size in (127, 2048, 83):
            chunk = rng.normal(0, 0.1, (block_size, 2)).astype(np.float32)
            expected = _scalar_equalize(
                chunk, frequencies, gains, engine._sample_rate, states
            )
            actual = engine._equalize(chunk)
            np.testing.assert_allclose(actual, expected, rtol=2e-6, atol=2e-7)

    def test_zero_gain_sos_bands_are_identity(self):
        engine = AudioEngine()
        engine._sample_rate = 48000
        engine.equalizer_config = EqualizerConfig(gains=[0.0] * 8)
        chunk = np.random.default_rng(23).normal(0, 0.2, (256, 2)).astype(np.float32)

        result = engine._equalize(chunk)

        np.testing.assert_array_equal(result, chunk)

    def test_motor_resampling_carries_source_offset_between_blocks(self):
        processor = VinylProcessor(10000)
        config = VinylConfig(
            motor_speed=1.01,
            wow_amount=0.0,
            flutter_amount=0.0,
            motor_random=0.0,
        )
        first = np.column_stack((np.arange(100), np.arange(100))).astype(np.float32)
        second = np.column_stack((np.arange(100, 200), np.arange(100, 200))).astype(np.float32)

        processor._apply_motor(first, config, 10000)
        self.assertAlmostEqual(processor._read_index, 1.0)
        next_block = processor._apply_motor(second, config, 10000)

        np.testing.assert_allclose(next_block[0], [101.0, 101.0])


if __name__ == "__main__":
    unittest.main()
