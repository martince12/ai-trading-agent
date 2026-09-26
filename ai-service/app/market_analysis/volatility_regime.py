"""Relative volatility classification from existing aligned realized volatility."""
from collections.abc import Sequence
from enum import StrEnum
from math import floor, isfinite
from numbers import Real

from .moving_averages import InsufficientHistoryError
from .policy import VOLATILITY_REGIME_POLICY


class VolatilityState(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


def _percentile(ordered: list[float], percentile: float) -> float:
    # Linear interpolation at zero-based rank (n - 1) * p / 100.
    rank = (len(ordered) - 1) * percentile / 100
    lower = floor(rank)
    fraction = rank - lower
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def classify_volatility_regime(series: Sequence[Real | None]) -> VolatilityState:
    """Classify the latest value against up to 100 available observations.

    Accept the chronological aligned output of realized_volatility20. Leading
    None values are warm-up only; internal/trailing gaps are rejected. Finite,
    nonnegative values are required. This helper needs one available observation;
    feature engineering retains the separate 100-candle readiness requirement.
    """
    available = []
    for value in series:
        if value is None:
            if available:
                raise ValueError("Volatility series may contain only leading None values")
            continue
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError("Volatility observations must be real numbers")
        value = float(value)
        if not isfinite(value) or value < 0:
            raise ValueError("Volatility observations must be finite and nonnegative")
        available.append(value)
    if not available:
        raise InsufficientHistoryError(1, 0, unit="volatility observations")
    latest = available[-1]
    sample = sorted(available[-VOLATILITY_REGIME_POLICY.lookback:])
    lower = _percentile(sample, VOLATILITY_REGIME_POLICY.lower_percentile)
    upper = _percentile(sample, VOLATILITY_REGIME_POLICY.upper_percentile)
    if latest < lower:
        return VolatilityState.LOW
    if latest > upper:
        return VolatilityState.HIGH
    return VolatilityState.MEDIUM
