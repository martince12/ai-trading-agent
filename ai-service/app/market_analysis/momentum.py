"""Price Rate of Change in percent, without directional classification."""
from collections.abc import Sequence
from math import isfinite
from numbers import Real

from .moving_averages import _prepare, _validate_period
from .policy import MOMENTUM10_POLICY, MOMENTUM20_POLICY, MomentumPolicy


def _momentum(closes: Sequence[Real], policy: MomentumPolicy) -> list[float | None]:
    _validate_period(policy.period)
    values = _prepare(closes, policy.minimum_closes)
    result: list[float | None] = [None] * policy.period
    for index in range(policy.period, len(values)):
        percentage = (values[index] / values[index - policy.period] - 1) * 100
        if not isfinite(percentage):
            raise ValueError("Momentum percentage exceeds the finite floating-point range")
        result.append(percentage)
    return result


def momentum(closes: Sequence[Real], period: int) -> list[float | None]:
    """Aligned percentage ROC over period observations; requires period + 1 closes.

    Inputs must be chronological, session-complete, finite positive daily closes.
    No values are changed or reordered. Too little history raises the shared
    InsufficientHistoryError; the first period output entries are None.
    """
    return _momentum(closes, MomentumPolicy(period=period))


def momentum10(closes: Sequence[Real]) -> list[float | None]:
    """Policy-backed 10-day percentage ROC, first available at index 10."""
    return _momentum(closes, MOMENTUM10_POLICY)


def momentum20(closes: Sequence[Real]) -> list[float | None]:
    """Policy-backed 20-day percentage ROC, first available at index 20."""
    return _momentum(closes, MOMENTUM20_POLICY)
