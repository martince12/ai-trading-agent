"""Latest deterministic derived features; not the final MarketFeatureVector."""
from collections.abc import Sequence
from dataclasses import dataclass, fields
from math import isfinite
from typing import cast

from app.market_data.models import Candle
from .bollinger_bands import bollinger_bands_20_2
from .macd import macd_12_26_9
from .momentum import momentum10, momentum20
from .moving_averages import ema20, ema50
from .policy import FEATURE_VECTOR_POLICY, get_indicator_policy
from .rsi import rsi14
from .support_resistance import detect_support_resistance
from .trend import TrendState, latest_trend
from .volatility import _prepare_candles, atr14, realized_volatility20
from .volatility_regime import VolatilityState, classify_volatility_regime
from .volume import analyze_volume20


@dataclass(frozen=True)
class EngineeredFeatures:
    ema20_above_ema50: bool
    ema_spread_pct: float
    price_above_ema20: bool
    price_above_ema50: bool
    rsi14: float
    macd: float
    macd_signal: float
    macd_histogram: float
    macd_above_signal: bool
    macd_histogram_positive: bool
    bollinger_position: float | None
    bollinger_bandwidth_pct: float
    volume_ratio_20: float | None
    volume_vs_average_pct: float | None
    atr14: float
    atr14_pct: float
    realized_volatility_20: float
    volatility_state: VolatilityState
    momentum_10_pct: float
    momentum_20_pct: float
    trend_state: TrendState
    trend_score: int
    ema20_slope_pct: float
    ema50_slope_pct: float
    nearest_support: float | None
    nearest_resistance: float | None
    distance_to_support_pct: float | None
    distance_to_resistance_pct: float | None


def engineer_features(candles: Sequence[Candle]) -> EngineeredFeatures:
    """Analyze the last candle using all supplied history, requiring at least 100.

    Reuses the feature-vector readiness policy and the existing OHLC validation.
    Input must contain one symbol's chronological, session-complete daily candles.
    No inputs are changed; no earlier candle is substituted for the latest one.
    Flat bands have undefined position (None) and zero bandwidth. Other optional
    values retain their source's None behavior. Comparisons use strict equality
    semantics, without rounding; Bollinger position is not clamped to [0, 1].
    """
    minimum = max(
        FEATURE_VECTOR_POLICY.minimum_candles,
        *(get_indicator_policy(indicator).minimum_closes
          for indicator in FEATURE_VECTOR_POLICY.required_indicators),
    )
    values = _prepare_candles(candles, minimum)
    # Also enforces unique daily market dates; preserves confirmed-swing semantics.
    levels = detect_support_resistance(values)
    closes = tuple(candle.close for candle in values)
    close = closes[-1]
    fast = cast(float, ema20(closes)[-1])
    slow = cast(float, ema50(closes)[-1])
    macd_result = macd_12_26_9(closes)
    line = cast(float, macd_result.macd[-1])
    signal = cast(float, macd_result.signal[-1])
    histogram = cast(float, macd_result.histogram[-1])
    bands = bollinger_bands_20_2(closes)
    middle, upper, lower = (cast(float, series[-1]) for series in (bands.middle, bands.upper, bands.lower))
    width = upper - lower
    volume = analyze_volume20(tuple(candle.volume for candle in values))
    atr_result = atr14(values)
    trend = latest_trend(closes)
    realized = realized_volatility20(closes)
    result = EngineeredFeatures(
        ema20_above_ema50=fast > slow,
        ema_spread_pct=(fast / slow - 1) * 100,
        price_above_ema20=close > fast,
        price_above_ema50=close > slow,
        rsi14=cast(float, rsi14(closes)[-1]),
        macd=line, macd_signal=signal, macd_histogram=histogram,
        macd_above_signal=line > signal, macd_histogram_positive=histogram > 0,
        bollinger_position=(close - lower) / width if width != 0 else None,
        bollinger_bandwidth_pct=width / middle * 100,
        volume_ratio_20=volume.volume_ratio[-1],
        volume_vs_average_pct=volume.volume_vs_average_pct[-1],
        atr14=cast(float, atr_result.atr[-1]),
        atr14_pct=cast(float, atr_result.atr_pct[-1]),
        realized_volatility_20=cast(float, realized[-1]),
        volatility_state=classify_volatility_regime(realized),
        momentum_10_pct=cast(float, momentum10(closes)[-1]),
        momentum_20_pct=cast(float, momentum20(closes)[-1]),
        trend_state=trend.state, trend_score=trend.score,
        ema20_slope_pct=trend.ema20_slope_pct, ema50_slope_pct=trend.ema50_slope_pct,
        nearest_support=levels.support.price if levels.support else None,
        nearest_resistance=levels.resistance.price if levels.resistance else None,
        distance_to_support_pct=levels.distance_to_support_pct,
        distance_to_resistance_pct=levels.distance_to_resistance_pct,
    )
    for field in fields(result):
        value = getattr(result, field.name)
        if isinstance(value, float) and not isfinite(value):
            raise ValueError(f"Feature {field.name} exceeds the finite floating-point range")
    return result
