"""Wilder RSI on chronological daily closes, aligned with the supplied history."""
from collections.abc import Sequence
from numbers import Real
from typing import cast

from .moving_averages import _mean, _prepare, _validate_period
from .policy import Indicator, RsiPolicy, get_indicator_policy


def _value(average_gain: float, average_loss: float, policy: RsiPolicy) -> float:
    if average_loss == 0:
        return policy.flat_market_value if average_gain == 0 else 100.0
    if average_gain == 0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def _rsi(closes: Sequence[Real], policy: RsiPolicy) -> list[float | None]:
    _validate_period(policy.period)
    if (policy.initialization != "mean_gain_and_loss_of_first_period_price_changes"
            or policy.smoothing != "wilder"):
        raise ValueError("Unsupported RSI initialization or smoothing policy")
    values = _prepare(closes, policy.minimum_closes)
    changes = tuple(values[index] - values[index - 1] for index in range(1, len(values)))
    seed_changes = changes[:policy.period]
    average_gain = _mean(tuple(max(change, 0.0) for change in seed_changes))
    average_loss = _mean(tuple(max(-change, 0.0) for change in seed_changes))
    result: list[float | None] = [None] * policy.period
    result.append(_value(average_gain, average_loss, policy))
    # Algebraically Wilder's (previous * (period - 1) + current) / period.
    # Divide the weights first to avoid overflowing the intermediate product.
    previous_weight = (policy.period - 1) / policy.period
    for change in changes[policy.period:]:
        average_gain = average_gain * previous_weight + max(change, 0.0) * policy.alpha
        average_loss = average_loss * previous_weight + max(-change, 0.0) * policy.alpha
        result.append(_value(average_gain, average_loss, policy))
    return result


def rsi(closes: Sequence[Real], period: int) -> list[float | None]:
    """Wilder RSI; the first period entries are None and flat markets return 50.

    Require period + 1 finite positive closes, otherwise raise the shared
    InsufficientHistoryError. Callers supply chronological, session-complete data.
    """
    return _rsi(closes, RsiPolicy(period=period))


def rsi14(closes: Sequence[Real]) -> list[float | None]:
    """Calculate RSI14 using the centralized V1 policy."""
    return _rsi(closes, cast(RsiPolicy, get_indicator_policy(Indicator.RSI14)))
