"""Deterministic daily volume measurements, without high/low classification."""
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from numbers import Real

from .moving_averages import InsufficientHistoryError, _sma_values, _validate_period
from .policy import SmaPolicy, VOLUME_POLICY


@dataclass(frozen=True)
class VolumeAnalysisResult:
    """Independent lists aligned with the original daily volume sequence."""

    average_volume_20: list[float | None]
    volume_ratio: list[float | None]
    volume_vs_average_pct: list[float | None]


def _prepare_volumes(volumes: Sequence[Real], period: int) -> tuple[float, ...]:
    _validate_period(period)
    if isinstance(volumes, (str, bytes)):
        raise TypeError("volumes must be a sequence of real numbers")
    values = []
    for index, volume in enumerate(volumes):
        if isinstance(volume, bool) or not isinstance(volume, Real):
            raise TypeError(f"volume at index {index} must be a real number")
        try:
            value = float(volume)
        except OverflowError:
            raise ValueError(f"volume at index {index} must be finite, nonnegative and below 1e308") from None
        # Matches the Phase 1 Candle.volume bounds; fractional and zero volumes are valid.
        if not isfinite(value) or not 0 <= value < 1e308:
            raise ValueError(f"volume at index {index} must be finite, nonnegative and below 1e308")
        values.append(value)
    if len(values) < period:
        raise InsufficientHistoryError(period, len(values), unit="volume values")
    return tuple(values)


def average_volume(volumes: Sequence[Real], period: int) -> list[float | None]:
    """Trailing mean including the current volume; first period - 1 values are None."""
    values = _prepare_volumes(volumes, period)
    return _sma_values(values, SmaPolicy(period=period))


def average_volume20(volumes: Sequence[Real]) -> list[float | None]:
    """Standard 20-day trailing average from the centralized volume policy."""
    return analyze_volume20(volumes).average_volume_20


def analyze_volume20(volumes: Sequence[Real]) -> VolumeAnalysisResult:
    """Compute average, ratio and percentage; zero averages leave ratio/pct as None.

    Callers supply chronological, session-complete daily volumes. Input is not
    changed or sorted. This function does not verify timestamps or classify volume.
    """
    if not VOLUME_POLICY.include_current or VOLUME_POLICY.zero_average_ratio is not None:
        raise ValueError("Unsupported volume analysis policy")
    values = _prepare_volumes(volumes, VOLUME_POLICY.minimum_values)
    averages = _sma_values(values, SmaPolicy(period=VOLUME_POLICY.period))
    ratios: list[float | None] = [None] * len(values)
    percentages: list[float | None] = [None] * len(values)
    for index, average in enumerate(averages):
        if average is not None and average != 0:
            ratios[index] = values[index] / average
            percentages[index] = (ratios[index] - 1) * 100
    return VolumeAnalysisResult(averages, ratios, percentages)
