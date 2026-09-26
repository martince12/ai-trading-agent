"""Immutable latest market state, assembled from the feature-engineering layer."""
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime, timezone

from app.market_data.models import Candle, MARKET_TZ
from .feature_engineering import EngineeredFeatures, engineer_features


@dataclass(frozen=True)
class MarketFeatureVector(EngineeredFeatures):
    """All engineered fields plus identity and time; construct via the builder."""

    symbol: str
    timestamp: datetime
    market_date: date


def build_market_feature_vector(candles: Sequence[Candle]) -> MarketFeatureVector:
    """Build the latest state without recalculating any indicators.

    engineer_features enforces the policy's 100-candle minimum, validated OHLCV,
    one symbol, chronological timestamps and unique New York market dates.
    All validation errors propagate unchanged. Optional values stay None, numeric
    values retain their types/precision, and trend state retains its enum type.
    """
    values = tuple(candles)
    engineered = engineer_features(values)
    latest = values[-1]
    return MarketFeatureVector(
        **{field.name: getattr(engineered, field.name) for field in fields(engineered)},
        symbol=latest.symbol,
        timestamp=latest.timestamp.astimezone(timezone.utc),
        market_date=latest.timestamp.astimezone(MARKET_TZ).date(),
    )
