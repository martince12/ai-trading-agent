"""Population-deviation Bollinger Bands on chronological daily closes."""
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from numbers import Real
from statistics import pstdev
from typing import cast

from .moving_averages import _prepare, _sma
from .policy import BollingerBandsPolicy, Indicator, SmaPolicy, get_indicator_policy


@dataclass(frozen=True)
class BollingerBandsResult:
    """Independent band lists aligned with the original close sequence."""

    middle: list[float | None]
    upper: list[float | None]
    lower: list[float | None]


def _bollinger_bands(closes: Sequence[Real], policy: BollingerBandsPolicy) -> BollingerBandsResult:
    multiplier = policy.standard_deviation_multiplier
    if isinstance(multiplier, bool) or not isinstance(multiplier, Real):
        raise TypeError("multiplier must be a real number")
    try:
        multiplier = float(multiplier)
    except OverflowError:
        raise ValueError("multiplier must be finite and nonnegative") from None
    if not isfinite(multiplier) or multiplier < 0:
        raise ValueError("multiplier must be finite and nonnegative")
    if policy.ddof != 0:
        raise ValueError("Bollinger Bands require population standard deviation (ddof=0)")
    values = _prepare(closes, policy.minimum_closes)
    middle = _sma(values, policy.center)
    period = policy.center.period
    upper: list[float | None] = [None] * (period - 1)
    lower: list[float | None] = [None] * (period - 1)
    for index in range(period - 1, len(values)):
        # pstdev uses population variance (divisor N), never sample variance (N-1).
        deviation = pstdev(values[index - period + 1:index + 1])
        width = multiplier * deviation
        center = cast(float, middle[index])
        high, low = center + width, center - width
        if not isfinite(high) or not isfinite(low):
            raise ValueError("Bollinger band exceeds the finite floating-point range")
        upper.append(high)
        lower.append(low)
    return BollingerBandsResult(middle=middle, upper=upper, lower=lower)


def bollinger_bands(closes: Sequence[Real], period: int, multiplier: Real) -> BollingerBandsResult:
    """Generic population bands; require period finite positive closes.

    Callers provide chronological, session-complete data. Insufficient input raises
    the shared InsufficientHistoryError; the first period - 1 positions are None.
    """
    return _bollinger_bands(closes, BollingerBandsPolicy(
        center=SmaPolicy(period=period), standard_deviation_multiplier=multiplier,
    ))


def bollinger_bands_20_2(closes: Sequence[Real]) -> BollingerBandsResult:
    """Standard Bollinger(20,2), using the centralized period, multiplier and ddof."""
    return _bollinger_bands(closes, cast(
        BollingerBandsPolicy, get_indicator_policy(Indicator.BOLLINGER_BANDS_20_2),
    ))
