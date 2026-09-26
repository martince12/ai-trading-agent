"""Confirmed swings and price clusters as of the last supplied daily candle."""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Literal

from app.market_data.models import Candle, MARKET_TZ
from .moving_averages import _mean
from .policy import SUPPORT_RESISTANCE_POLICY, SupportResistancePolicy
from .volatility import _prepare_candles


@dataclass(frozen=True)
class SwingPoint:
    kind: Literal["HIGH", "LOW"]
    price: float
    index: int
    market_date: date
    confirmed_at_index: int


@dataclass(frozen=True)
class PriceLevel:
    price: float
    touches: int
    first_touch_index: int
    last_touch_index: int
    first_touch_date: date
    last_touch_date: date


@dataclass(frozen=True)
class SupportResistanceResult:
    latest_close: float
    swings: tuple[SwingPoint, ...]
    clusters: tuple[PriceLevel, ...]
    support: PriceLevel | None
    resistance: PriceLevel | None
    distance_to_support_pct: float | None
    distance_to_resistance_pct: float | None


def _clusters(points: list[SwingPoint], tolerance_pct: float) -> tuple[PriceLevel, ...]:
    groups: list[list[SwingPoint]] = []
    for point in sorted(points, key=lambda point: (point.price, point.index, point.kind)):
        # Anchor to the minimum, preventing chains from spanning the tolerance.
        if not groups or (point.price - groups[-1][0].price) / groups[-1][0].price > tolerance_pct / 100:
            groups.append([point])
        else:
            groups[-1].append(point)
    result = []
    for group in groups:
        first = min(group, key=lambda point: point.index)
        last = max(group, key=lambda point: point.index)
        result.append(PriceLevel(
            price=_mean(tuple(point.price for point in group)),
            touches=len({point.index for point in group}),
            first_touch_index=first.index, last_touch_index=last.index,
            first_touch_date=first.market_date, last_touch_date=last.market_date,
        ))
    return tuple(result)


def detect_support_resistance(
    candles: Sequence[Candle],
    policy: SupportResistancePolicy = SUPPORT_RESISTANCE_POLICY,
) -> SupportResistanceResult:
    """Latest snapshot; strict swings need a full window on both sides.

    Clusters pool highs/lows, count distinct candles, and include singleton levels
    for audit. Only clusters meeting minimum_touches can be selected. Levels equal
    to the latest close are neither support nor resistance. Distances are positive
    percentages of latest close. History shorter than 2*window+1 raises the shared
    InsufficientHistoryError; sufficient history without levels returns None.
    """
    values = _prepare_candles(candles, policy.minimum_candles)
    dates = tuple(candle.timestamp.astimezone(MARKET_TZ).date() for candle in values)
    if any(current <= previous for previous, current in zip(dates, dates[1:])):
        raise ValueError("Daily candles must have strictly increasing New York market dates")
    window = policy.swing_window
    points = []
    for index in range(window, len(values) - window):
        current = values[index]
        neighbors = values[index-window:index] + values[index+1:index+window+1]
        if all(current.high > neighbor.high for neighbor in neighbors):
            points.append(SwingPoint("HIGH", current.high, index, dates[index], index + window))
        if all(current.low < neighbor.low for neighbor in neighbors):
            points.append(SwingPoint("LOW", current.low, index, dates[index], index + window))
    clusters = _clusters(points, policy.cluster_tolerance_pct)
    close = values[-1].close
    valid = tuple(level for level in clusters if level.touches >= policy.minimum_touches)
    support = max((level for level in valid if level.price < close), key=lambda level: level.price, default=None)
    resistance = min((level for level in valid if level.price > close), key=lambda level: level.price, default=None)
    support_pct = (close - support.price) / close * 100 if support else None
    resistance_pct = (resistance.price - close) / close * 100 if resistance else None
    if any(value is not None and not isfinite(value) for value in (support_pct, resistance_pct)):
        raise ValueError("Level distance exceeds the finite floating-point range")
    return SupportResistanceResult(
        latest_close=close, swings=tuple(points), clusters=clusters,
        support=support, resistance=resistance,
        distance_to_support_pct=support_pct, distance_to_resistance_pct=resistance_pct,
    )
