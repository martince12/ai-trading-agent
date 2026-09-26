"""Six equally weighted deterministic trend signals; no trading decisions."""
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from numbers import Real
from typing import cast

from .macd import macd_12_26_9
from .momentum import momentum, momentum20
from .moving_averages import _prepare, ema20, ema50
from .policy import Indicator, TREND_POLICY, get_indicator_policy


class TrendState(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class TrendSignals:
    close_vs_ema20: int
    ema20_vs_ema50: int
    ema20_slope: int
    ema50_slope: int
    macd_histogram: int
    momentum20: int

    @property
    def score(self) -> int:
        return (self.close_vs_ema20 + self.ema20_vs_ema50 + self.ema20_slope
                + self.ema50_slope + self.macd_histogram + self.momentum20)


@dataclass(frozen=True)
class TrendResult:
    state: TrendState
    score: int
    signals: TrendSignals
    ema20_slope_pct: float
    ema50_slope_pct: float


def _compare(left: float, right: float = 0.0) -> int:
    return int(left > right) - int(left < right)


def _classify(score: int) -> TrendState:
    if score >= TREND_POLICY.bullish_threshold:
        return TrendState.BULLISH
    if score <= TREND_POLICY.bearish_threshold:
        return TrendState.BEARISH
    return TrendState.NEUTRAL


def _slope(values: list[float | None], indicator: Indicator) -> list[float | None]:
    first = get_indicator_policy(indicator).minimum_closes - 1
    available = tuple(cast(float, value) for value in values[first:])
    # Reuse percentage ROC, preserving the original candle alignment.
    return [None] * first + momentum(available, TREND_POLICY.slope_lookback)


def detect_trend(closes: Sequence[Real]) -> list[TrendResult | None]:
    """Aligned V1 trend results, first available at index 54 (55 closes).

    Inputs are chronological, validated daily closes. Price validation and the
    InsufficientHistoryError convention are shared with existing indicators.
    """
    values = _prepare(closes, TREND_POLICY.minimum_closes)
    fast = ema20(values)
    slow = ema50(values)
    histogram = macd_12_26_9(values).histogram
    price_momentum = momentum20(values)
    fast_slope = _slope(fast, Indicator.EMA20)
    slow_slope = _slope(slow, Indicator.EMA50)
    result: list[TrendResult | None] = [None] * (TREND_POLICY.minimum_closes - 1)
    for index in range(TREND_POLICY.minimum_closes - 1, len(values)):
        ema_fast, ema_slow = cast(float, fast[index]), cast(float, slow[index])
        slope_fast, slope_slow = cast(float, fast_slope[index]), cast(float, slow_slope[index])
        signals = TrendSignals(
            close_vs_ema20=_compare(values[index], ema_fast),
            ema20_vs_ema50=_compare(ema_fast, ema_slow),
            ema20_slope=_compare(slope_fast),
            ema50_slope=_compare(slope_slow),
            macd_histogram=_compare(cast(float, histogram[index])),
            momentum20=_compare(cast(float, price_momentum[index])),
        )
        result.append(TrendResult(
            state=_classify(signals.score), score=signals.score, signals=signals,
            ema20_slope_pct=slope_fast, ema50_slope_pct=slope_slow,
        ))
    return result


def latest_trend(closes: Sequence[Real]) -> TrendResult:
    """Latest V1 trend; requires the same full history as detect_trend."""
    return cast(TrendResult, detect_trend(closes)[-1])
