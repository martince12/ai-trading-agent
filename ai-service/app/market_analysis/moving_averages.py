"""Pure SMA/EMA calculations on oldest-to-newest, validated daily closes.

Results align with the input: the first period - 1 entries are None. Callers
provide chronological, session-complete data; a close-only sequence has no dates
with which to verify ordering or gaps. No input values are changed or reordered.
"""
from collections.abc import Sequence
from math import fsum, isfinite
from numbers import Real
from typing import cast

from .policy import EmaPolicy, Indicator, SmaPolicy, get_indicator_policy


class InsufficientHistoryError(ValueError):
    """The input cannot produce even one complete indicator value."""

    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(f"Insufficient history: requires {required} closes; received {available}")


def _validate_period(period: int) -> None:
    if isinstance(period, bool) or not isinstance(period, int):
        raise TypeError("period must be an integer")
    if period <= 0:
        raise ValueError("period must be positive")


def _prepare(closes: Sequence[Real], period: int) -> tuple[float, ...]:
    _validate_period(period)
    if isinstance(closes, (str, bytes)):
        raise TypeError("closes must be a sequence of real numbers")
    values = []
    for index, close in enumerate(closes):
        if isinstance(close, bool) or not isinstance(close, Real):
            raise TypeError(f"close at index {index} must be a real number")
        try:
            value = float(close)
        except OverflowError:
            raise ValueError(f"close at index {index} must be finite and positive") from None
        if not isfinite(value) or value <= 0:
            raise ValueError(f"close at index {index} must be finite and positive")
        values.append(value)
    if len(values) < period:
        raise InsufficientHistoryError(required=period, available=len(values))
    return tuple(values)


def _mean(values: tuple[float, ...]) -> float:
    # Scaling before summing avoids overflowing an otherwise representable mean.
    return fsum(value / len(values) for value in values)


def _sma(closes: Sequence[Real], policy: SmaPolicy) -> list[float | None]:
    values = _prepare(closes, policy.minimum_closes)
    result: list[float | None] = [None] * (policy.period - 1)
    for end in range(policy.period, len(values) + 1):
        result.append(_mean(values[end - policy.period:end]))
    return result


def _ema(closes: Sequence[Real], policy: EmaPolicy) -> list[float | None]:
    values = _prepare(closes, policy.minimum_closes)
    return _ema_values(values, policy)


def _ema_values(values: tuple[float, ...], policy: EmaPolicy) -> list[float | None]:
    """Shared EMA arithmetic for prepared closes or finite signed indicator values.

    Internal callers supply at least policy.minimum_closes values. Public close-price
    validation stays in _ema; derived series such as MACD may contain zero/negatives.
    """
    if policy.initialization != "sma_of_first_period_values":
        raise ValueError("Unsupported EMA initialization policy")
    previous = _mean(values[:policy.period])
    result: list[float | None] = [None] * (policy.period - 1) + [previous]
    alpha = policy.alpha
    for close in values[policy.period:]:
        previous = previous + alpha * (close - previous)
        result.append(previous)
    return result


def sma(closes: Sequence[Real], period: int) -> list[float | None]:
    """Trailing arithmetic mean; raise InsufficientHistoryError below period closes."""
    return _sma(closes, SmaPolicy(period=period))


def ema(closes: Sequence[Real], period: int) -> list[float | None]:
    """SMA-seeded EMA using EmaPolicy's alpha; never seed from the first close alone."""
    return _ema(closes, EmaPolicy(period=period))


def sma20(closes: Sequence[Real]) -> list[float | None]:
    return _sma(closes, cast(SmaPolicy, get_indicator_policy(Indicator.SMA20)))


def sma50(closes: Sequence[Real]) -> list[float | None]:
    return _sma(closes, cast(SmaPolicy, get_indicator_policy(Indicator.SMA50)))


def ema20(closes: Sequence[Real]) -> list[float | None]:
    return _ema(closes, cast(EmaPolicy, get_indicator_policy(Indicator.EMA20)))


def ema50(closes: Sequence[Real]) -> list[float | None]:
    return _ema(closes, cast(EmaPolicy, get_indicator_policy(Indicator.EMA50)))
