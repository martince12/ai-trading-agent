"""Aligned MACD, signal and histogram using the project's shared EMA calculation."""
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real
from typing import cast

from .moving_averages import _ema_values, _prepare, _validate_period
from .policy import EmaPolicy, Indicator, MacdPolicy, get_indicator_policy


@dataclass(frozen=True)
class MacdResult:
    """Three independently owned lists aligned with the original close sequence."""

    macd: list[float | None]
    signal: list[float | None]
    histogram: list[float | None]


def _macd(closes: Sequence[Real], policy: MacdPolicy) -> MacdResult:
    for component in (policy.fast, policy.slow, policy.signal):
        _validate_period(component.period)
    if (policy.signal_input != "available_macd_values"
            or policy.macd_definition != "fast_ema_minus_slow_ema"
            or policy.histogram_definition != "macd_minus_signal"):
        raise ValueError("Unsupported MACD calculation policy")
    # Validate closes once, requiring enough data for at least one complete result.
    values = _prepare(closes, policy.minimum_closes)
    fast = _ema_values(values, policy.fast)
    slow = _ema_values(values, policy.slow)
    line = [None if f is None or s is None else f - s
            for f, s in zip(fast, slow, strict=True)]
    first_macd_index = policy.macd_minimum_closes - 1
    available_macd = tuple(cast(float, value) for value in line[first_macd_index:])
    # Only available MACD values enter the seed; leading None values are never zero-filled.
    signal = [None] * first_macd_index + _ema_values(available_macd, policy.signal)
    histogram = [None if m is None or s is None else m - s
                 for m, s in zip(line, signal, strict=True)]
    return MacdResult(macd=line, signal=signal, histogram=histogram)


def macd(closes: Sequence[Real], fast_period: int, slow_period: int,
         signal_period: int) -> MacdResult:
    """Generic SMA-seeded MACD; require max(fast, slow) + signal - 1 closes.

    Periods must be positive integers. Callers supply chronological, session-complete
    closes. Insufficient inputs raise the shared InsufficientHistoryError.
    """
    return _macd(closes, MacdPolicy(
        fast=EmaPolicy(period=fast_period), slow=EmaPolicy(period=slow_period),
        signal=EmaPolicy(period=signal_period),
    ))


def macd_12_26_9(closes: Sequence[Real]) -> MacdResult:
    """Standard MACD from centralized policy; complete output needs 34 closes."""
    return _macd(closes, cast(MacdPolicy, get_indicator_policy(Indicator.MACD_12_26_9)))
