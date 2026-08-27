import unittest

import numpy as np

from audio.engine import AudioEngine


class SpatialPhaseTests(unittest.TestCase):
    def make_engine(self):
        engine = AudioEngine()
        engine.config.phase_to_surround = True
        engine.config.phase_rear_blend = 1.0
        engine.config.mix_to_lfe = True
        return engine

    def test_in_phase_signal_stays_at_the_front(self):
        chunk = np.ones((64, 2), dtype=np.float32)

        output = self.make_engine()._spatialize(chunk)

        np.testing.assert_allclose(output[:, 4:6], 0.0)
        self.assertGreater(np.max(np.abs(output[:, :2])), 0.0)

    def test_out_of_phase_signal_goes_to_surrounds(self):
        chunk = np.column_stack((np.ones(64), -np.ones(64))).astype(np.float32)

        output = self.make_engine()._spatialize(chunk)

        np.testing.assert_allclose(output[:, :4], 0.0)
        self.assertGreater(np.max(np.abs(output[:, 4:6])), 0.0)

    def test_lfe_is_independent_from_phase_routing(self):
        chunk = np.full((64, 2), 0.5, dtype=np.float32)
        phase_engine = self.make_engine()
        plain_engine = self.make_engine()
        plain_engine.config.phase_to_surround = False
        for engine in (phase_engine, plain_engine):
            engine.config.gain_lfe = 1.0
            engine.config.lfe_gain = 1.0

        with_lfe = phase_engine._spatialize(chunk)[:, 3]
        without_phase = plain_engine._spatialize(chunk)[:, 3]

        np.testing.assert_allclose(with_lfe, without_phase)


if __name__ == "__main__":
    unittest.main()