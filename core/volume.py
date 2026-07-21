import math


MIN_DB = -60.0
MAX_DB = 0.0
SLIDER_MIN = 0
SLIDER_MAX = 100


def slider_to_gain(value: int | float) -> float:
    """Map a slider value to a logarithmic gain in linear amplitude."""
    clamped = max(SLIDER_MIN, min(SLIDER_MAX, float(value)))
    if clamped <= SLIDER_MIN:
        return 0.0
    db = MIN_DB + (clamped / SLIDER_MAX) * (MAX_DB - MIN_DB)
    return 10 ** (db / 10.0)


def gain_to_slider_value(gain: float) -> int:
    """Map a linear gain to a slider value using the inverse logarithmic curve."""
    clamped = max(0.0, min(1.0, float(gain)))
    if clamped <= 0.0:
        return 0
    db = 10.0 * math.log10(clamped)
    value = ((db - MIN_DB) / (MAX_DB - MIN_DB)) * SLIDER_MAX
    return int(round(max(SLIDER_MIN, min(SLIDER_MAX, value))))
