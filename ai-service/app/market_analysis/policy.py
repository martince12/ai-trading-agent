"""V1 initialization and count-based readiness; no indicator calculations.

Counts represent validated, chronological daily candles with one close per candle.
The caller remains responsible for data quality and trading-session completeness.
"""
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class Indicator(StrEnum):
    SMA20 = "SMA20"
    SMA50 = "SMA50"
    EMA20 = "EMA20"
    EMA50 = "EMA50"
    RSI14 = "RSI14"
    MACD_12_26_9 = "MACD(12,26,9)"
    BOLLINGER_BANDS_20_2 = "BollingerBands(20,2)"


@dataclass(frozen=True)
class SmaPolicy:
    period: int

    @property
    def minimum_closes(self) -> int:
        return self.period


@dataclass(frozen=True)
class EmaPolicy:
    period: int
    initialization: str = "sma_of_first_period_values"

    @property
    def minimum_closes(self) -> int:
        return self.period

    @property
    def alpha(self) -> float:
        return 2 / (self.period + 1)


@dataclass(frozen=True)
class RsiPolicy:
    period: int
    initialization: str = "mean_gain_and_loss_of_first_period_price_changes"
    smoothing: str = "wilder"
    flat_market_value: float = 50.0

    @property
    def minimum_closes(self) -> int:
        return self.period + 1

    @property
    def alpha(self) -> float:
        return 1 / self.period


@dataclass(frozen=True)
class MacdPolicy:
    fast: EmaPolicy
    slow: EmaPolicy
    signal: EmaPolicy
    signal_input: str = "available_macd_values"
    macd_definition: str = "fast_ema_minus_slow_ema"
    histogram_definition: str = "macd_minus_signal"

    @property
    def macd_minimum_closes(self) -> int:
        return max(self.fast.minimum_closes, self.slow.minimum_closes)

    @property
    def minimum_closes(self) -> int:
        # The first available MACD value is also the first signal-seed sample.
        return self.macd_minimum_closes + self.signal.period - 1


@dataclass(frozen=True)
class BollingerBandsPolicy:
    center: SmaPolicy
    standard_deviation_multiplier: float = 2.0
    ddof: int = 0

    @property
    def minimum_closes(self) -> int:
        return self.center.minimum_closes


IndicatorPolicy = SmaPolicy | EmaPolicy | RsiPolicy | MacdPolicy | BollingerBandsPolicy

_SMA20 = SmaPolicy(period=20)
_SMA50 = SmaPolicy(period=50)

INDICATOR_POLICIES: Mapping[Indicator, IndicatorPolicy] = MappingProxyType({
    Indicator.SMA20: _SMA20,
    Indicator.SMA50: _SMA50,
    Indicator.EMA20: EmaPolicy(period=_SMA20.period),
    Indicator.EMA50: EmaPolicy(period=_SMA50.period),
    Indicator.RSI14: RsiPolicy(period=14),
    Indicator.MACD_12_26_9: MacdPolicy(
        fast=EmaPolicy(period=12), slow=EmaPolicy(period=26), signal=EmaPolicy(period=9),
    ),
    Indicator.BOLLINGER_BANDS_20_2: BollingerBandsPolicy(center=_SMA20),
})


@dataclass(frozen=True)
class FeatureVectorPolicy:
    """Readiness contract for the future MarketFeatureVector, not a value model."""

    minimum_candles: int = 100
    required_indicators: tuple[Indicator, ...] = tuple(Indicator)


FEATURE_VECTOR_POLICY = FeatureVectorPolicy()


@dataclass(frozen=True)
class VolumePolicy:
    period: int = 20
    include_current: bool = True
    zero_average_ratio: None = None

    @property
    def minimum_values(self) -> int:
        return self.period


VOLUME_POLICY = VolumePolicy()


@dataclass(frozen=True)
class AtrPolicy:
    period: int = 14
    initialization: str = "mean_of_first_period_true_ranges"
    first_true_range: str = "high_minus_low"
    smoothing: str = "wilder"

    @property
    def minimum_candles(self) -> int:
        return self.period

    @property
    def alpha(self) -> float:
        return 1 / self.period


@dataclass(frozen=True)
class RealizedVolatilityPolicy:
    return_period: int = 20
    annualization_factor: int = 252
    ddof: int = 0

    @property
    def minimum_closes(self) -> int:
        return self.return_period + 1


ATR_POLICY = AtrPolicy()
REALIZED_VOLATILITY_POLICY = RealizedVolatilityPolicy()


@dataclass(frozen=True)
class MomentumPolicy:
    period: int

    @property
    def minimum_closes(self) -> int:
        return self.period + 1


MOMENTUM10_POLICY = MomentumPolicy(period=10)
MOMENTUM20_POLICY = MomentumPolicy(period=20)


@dataclass(frozen=True)
class TrendPolicy:
    slope_lookback: int = 5
    bullish_threshold: int = 3
    bearish_threshold: int = -3

    @property
    def minimum_closes(self) -> int:
        return max(
            INDICATOR_POLICIES[Indicator.EMA20].minimum_closes + self.slope_lookback,
            INDICATOR_POLICIES[Indicator.EMA50].minimum_closes + self.slope_lookback,
            INDICATOR_POLICIES[Indicator.MACD_12_26_9].minimum_closes,
            MOMENTUM20_POLICY.minimum_closes,
        )


TREND_POLICY = TrendPolicy()


def is_trend_ready(candle_count: int) -> bool:
    _validate_candle_count(candle_count)
    return candle_count >= TREND_POLICY.minimum_closes


def is_momentum10_ready(candle_count: int) -> bool:
    _validate_candle_count(candle_count)
    return candle_count >= MOMENTUM10_POLICY.minimum_closes


def is_momentum20_ready(candle_count: int) -> bool:
    _validate_candle_count(candle_count)
    return candle_count >= MOMENTUM20_POLICY.minimum_closes


def is_atr_ready(candle_count: int) -> bool:
    _validate_candle_count(candle_count)
    return candle_count >= ATR_POLICY.minimum_candles


def is_realized_volatility_ready(candle_count: int) -> bool:
    _validate_candle_count(candle_count)
    return candle_count >= REALIZED_VOLATILITY_POLICY.minimum_closes


def is_volume_ready(candle_count: int) -> bool:
    """Count readiness only; an all-zero window still has an undefined ratio."""
    _validate_candle_count(candle_count)
    return candle_count >= VOLUME_POLICY.minimum_values


def get_indicator_policy(indicator: Indicator | str) -> IndicatorPolicy:
    """Accept an Indicator member or its exact string value; reject unknown names."""
    return INDICATOR_POLICIES[Indicator(indicator)]


def _validate_candle_count(candle_count: int) -> None:
    if isinstance(candle_count, bool) or not isinstance(candle_count, int):
        raise TypeError("candle_count must be an integer")
    if candle_count < 0:
        raise ValueError("candle_count must be nonnegative")


def is_indicator_ready(indicator: Indicator | str, candle_count: int) -> bool:
    """Whether enough closes exist for the indicator's complete first output."""
    _validate_candle_count(candle_count)
    return candle_count >= get_indicator_policy(indicator).minimum_closes


def is_feature_vector_ready(candle_count: int) -> bool:
    """Require the V1 100-candle floor and every constituent indicator's readiness."""
    _validate_candle_count(candle_count)
    return candle_count >= FEATURE_VECTOR_POLICY.minimum_candles and all(
        is_indicator_ready(indicator, candle_count)
        for indicator in FEATURE_VECTOR_POLICY.required_indicators
    )
