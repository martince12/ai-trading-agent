"""Wilder ATR and annualized population volatility of daily log returns."""
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite, log, log1p, sqrt
from numbers import Real
from statistics import pstdev

from app.market_data.models import Candle
from .moving_averages import InsufficientHistoryError, _mean, _prepare, _validate_period
from .policy import (
    ATR_POLICY, REALIZED_VOLATILITY_POLICY, AtrPolicy, RealizedVolatilityPolicy,
)


@dataclass(frozen=True)
class AtrResult:
    """ATR in price units and ATR percentage, aligned with input candles."""

    atr: list[float | None]
    atr_pct: list[float | None]


def _prepare_candles(candles: Sequence[Candle], minimum: int) -> tuple[Candle, ...]:
    values = tuple(candles)
    previous = None
    for candle in values:
        if not isinstance(candle, Candle):
            raise TypeError("ATR input must contain Candle objects")
        # Revalidate even objects produced with model_construct/model_copy.
        Candle.model_validate(candle.model_dump())
        if previous is not None:
            if candle.symbol != previous.symbol:
                raise ValueError("ATR candles must belong to one symbol")
            if candle.timestamp <= previous.timestamp:
                raise ValueError("ATR candles must have strictly increasing timestamps")
        previous = candle
    if len(values) < minimum:
        raise InsufficientHistoryError(minimum, len(values), unit="candles")
    return values


def _true_ranges(candles: tuple[Candle, ...]) -> tuple[float, ...]:
    ranges = [candles[0].high - candles[0].low]
    for previous, current in zip(candles, candles[1:]):
        ranges.append(max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        ))
    return tuple(ranges)


def true_range(candles: Sequence[Candle]) -> list[float]:
    """Aligned True Range, including high-low for the first candle; requires one candle."""
    return list(_true_ranges(_prepare_candles(candles, 1)))


def _atr(candles: Sequence[Candle], policy: AtrPolicy) -> AtrResult:
    _validate_period(policy.period)
    if (policy.initialization != "mean_of_first_period_true_ranges"
            or policy.first_true_range != "high_minus_low" or policy.smoothing != "wilder"):
        raise ValueError("Unsupported ATR calculation policy")
    values = _prepare_candles(candles, policy.minimum_candles)
    ranges = _true_ranges(values)
    previous = _mean(ranges[:policy.period])
    averages: list[float | None] = [None] * (policy.period - 1) + [previous]
    # Wilder recurrence evaluated as weighted terms to avoid product overflow.
    previous_weight = (policy.period - 1) / policy.period
    for current in ranges[policy.period:]:
        previous = previous * previous_weight + current * policy.alpha
        averages.append(previous)
    percentages: list[float | None] = [None] * (policy.period - 1)
    for index in range(policy.period - 1, len(values)):
        percentage = averages[index] / values[index].close * 100
        if not isfinite(percentage):
            raise ValueError("ATR percentage exceeds the finite floating-point range")
        percentages.append(percentage)
    return AtrResult(atr=averages, atr_pct=percentages)


def atr(candles: Sequence[Candle], period: int) -> AtrResult:
    """Generic Wilder ATR; require period candles and seed from their True Ranges."""
    return _atr(candles, AtrPolicy(period=period))


def atr14(candles: Sequence[Candle]) -> AtrResult:
    """ATR14 and ATR percentage using the centralized policy."""
    return _atr(candles, ATR_POLICY)


def _log_returns(values: tuple[float, ...]) -> tuple[float, ...]:
    returns = []
    for previous, current in zip(values, values[1:]):
        relative_change = (current - previous) / previous
        # log1p preserves small changes; log differences avoid ratio overflow/underflow.
        value = (log1p(relative_change) if isfinite(relative_change) and relative_change > -1
                 else log(current) - log(previous))
        returns.append(value)
    return tuple(returns)


def log_returns(closes: Sequence[Real]) -> list[float | None]:
    """Aligned ln(current/previous), with None at index zero; requires two closes."""
    return [None, *_log_returns(_prepare(closes, 2))]


def _realized_volatility(closes: Sequence[Real], policy: RealizedVolatilityPolicy) -> list[float | None]:
    _validate_period(policy.return_period)
    _validate_period(policy.annualization_factor)
    if policy.ddof != 0:
        raise ValueError("Realized volatility requires population standard deviation (ddof=0)")
    values = _prepare(closes, policy.minimum_closes)
    returns = _log_returns(values)
    result: list[float | None] = [None] * policy.return_period
    scale = sqrt(policy.annualization_factor)
    for end in range(policy.return_period, len(returns) + 1):
        result.append(pstdev(returns[end - policy.return_period:end]) * scale)
    return result


def realized_volatility(closes: Sequence[Real], return_period: int,
                        annualization_factor: int) -> list[float | None]:
    """Population SD of trailing log returns, annualized; result is decimal, not percent."""
    return _realized_volatility(closes, RealizedVolatilityPolicy(
        return_period=return_period, annualization_factor=annualization_factor,
    ))


def realized_volatility20(closes: Sequence[Real]) -> list[float | None]:
    """Policy-backed 20-return volatility, annualized by sqrt(252); needs 21 closes."""
    return _realized_volatility(closes, REALIZED_VOLATILITY_POLICY)
