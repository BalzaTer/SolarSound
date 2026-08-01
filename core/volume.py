import math


MIN_DB = -60.0
MAX_DB = 0.0
SLIDER_MIN = 0
SLIDER_NORMAL_MAX = 100
SLIDER_MAX = 150
BOOST_GAIN_MAX = 1.5


def slider_to_gain(value: int | float) -> float:
    """Map a slider value to a linear gain with extra headroom above 100."""
    clamped = max(SLIDER_MIN, min(SLIDER_MAX, float(value)))
    if clamped <= SLIDER_MIN:
        return 0.0
    if clamped <= SLIDER_NORMAL_MAX:
        db = MIN_DB + (clamped / SLIDER_NORMAL_MAX) * (MAX_DB - MIN_DB)
        return 10 ** (db / 10.0)
    boost = clamped - SLIDER_NORMAL_MAX
    return 1.0 + (boost / (SLIDER_MAX - SLIDER_NORMAL_MAX)) * (BOOST_GAIN_MAX - 1.0)


def gain_to_slider_value(gain: float) -> int:
    """Map a linear gain to a slider value with extra headroom above 1.0."""
    clamped = max(0.0, min(BOOST_GAIN_MAX, float(gain)))
    if clamped <= 0.0:
        return 0
    if clamped <= 1.0:
        db = 10.0 * math.log10(clamped)
        value = ((db - MIN_DB) / (MAX_DB - MIN_DB)) * SLIDER_NORMAL_MAX
        return int(round(max(SLIDER_MIN, min(SLIDER_NORMAL_MAX, value))))
    boost = clamped - 1.0
    value = SLIDER_NORMAL_MAX + (boost / (BOOST_GAIN_MAX - 1.0)) * (SLIDER_MAX - SLIDER_NORMAL_MAX)
    return int(round(max(SLIDER_NORMAL_MAX, min(SLIDER_MAX, value))))
