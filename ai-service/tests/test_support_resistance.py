import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

from app.market_data.models import Candle
from app.market_analysis.moving_averages import InsufficientHistoryError
from app.market_analysis.policy import (
    SUPPORT_RESISTANCE_POLICY, SupportResistancePolicy, is_support_resistance_ready,
)
from app.market_analysis.support_resistance import detect_support_resistance


def candles(lows=(), highs=(), close=110, size=None):
    """Isolated extrema four candles apart, surrounded by a flat OHLC baseline."""
    count = size if size is not None else 4 * max(len(lows), len(highs), 1) + 3
    result = []
    for index in range(count):
        slot = (index - 2) // 4
        low = lows[slot] if index % 4 == 2 and 0 <= slot < len(lows) else 105
        high = highs[slot] if index % 4 == 2 and 0 <= slot < len(highs) else 115
        current = close if index == count - 1 else 110
        result.append(Candle(
            symbol="AAPL", timestamp=datetime(2020, 1, 2, 5, tzinfo=timezone.utc) + timedelta(days=index),
            open=current, high=max(high, current), low=min(low, current), close=current, volume=0,
        ))
    return result


class SupportResistanceTests(unittest.TestCase):
    def test_repeated_support_and_touch_metadata(self):
        result = detect_support_resistance(candles(lows=(100, 100)))
        self.assertEqual(result.support.price, 100)
        self.assertEqual(result.support.touches, 2)
        self.assertEqual((result.support.first_touch_index, result.support.last_touch_index), (2, 6))
        self.assertEqual(result.support.first_touch_date.isoformat(), "2020-01-04")
        self.assertEqual(result.support.last_touch_date.isoformat(), "2020-01-08")

    def test_repeated_resistance(self):
        result = detect_support_resistance(candles(highs=(120, 120)))
        self.assertEqual((result.resistance.price, result.resistance.touches), (120, 2))

    def test_nearby_swings_cluster_at_arithmetic_mean(self):
        result = detect_support_resistance(candles(lows=(100, 100.5, 100.75)))
        self.assertEqual(len(result.clusters), 1)
        self.assertAlmostEqual(result.support.price, (100 + 100.5 + 100.75) / 3)
        self.assertEqual(result.support.touches, 3)

    def test_outside_tolerance_and_chaining_remain_separate(self):
        result = detect_support_resistance(candles(lows=(100, 100.5, 101.5)))
        self.assertEqual([(level.price, level.touches) for level in result.clusters], [(100.25, 2), (101.5, 1)])
        self.assertEqual(result.support.price, 100.25)

    def test_exact_tolerance_boundary_inclusive(self):
        result = detect_support_resistance(candles(lows=(100, 101)))
        self.assertEqual((result.support.price, result.support.touches), (100.5, 2))

    def test_nearest_support(self):
        result = detect_support_resistance(candles(lows=(100, 100, 103, 103)))
        self.assertEqual(result.support.price, 103)

    def test_nearest_resistance(self):
        result = detect_support_resistance(candles(highs=(120, 120, 117, 117)))
        self.assertEqual(result.resistance.price, 117)

    def test_no_valid_support(self):
        result = detect_support_resistance(candles(highs=(120, 120)))
        self.assertIsNone(result.support)
        self.assertIsNone(result.distance_to_support_pct)

    def test_no_valid_resistance(self):
        result = detect_support_resistance(candles(lows=(100, 100)))
        self.assertIsNone(result.resistance)
        self.assertIsNone(result.distance_to_resistance_pct)

    def test_minimum_touches_and_custom_policy(self):
        values = candles(lows=(100, 100), highs=(120,))
        result = detect_support_resistance(values)
        self.assertIsNotNone(result.support)
        self.assertIsNone(result.resistance)
        result = detect_support_resistance(values, SupportResistancePolicy(minimum_touches=3))
        self.assertIsNone(result.support)
        result = detect_support_resistance(values, SupportResistancePolicy(minimum_touches=1))
        self.assertEqual(result.resistance.price, 120)
        result = detect_support_resistance(candles(lows=(100, 100.5)), SupportResistancePolicy(cluster_tolerance_pct=0))
        self.assertIsNone(result.support)
        self.assertEqual(len(result.clusters), 2)

    def test_distance_percentages(self):
        result = detect_support_resistance(candles(lows=(100, 100), highs=(120, 120)))
        self.assertEqual(result.latest_close, 110)
        self.assertAlmostEqual(result.distance_to_support_pct, 100 / 11)
        self.assertAlmostEqual(result.distance_to_resistance_pct, 100 / 11)

    def test_equal_to_close_is_neither_support_nor_resistance(self):
        result = detect_support_resistance(candles(lows=(100, 100), close=100))
        self.assertEqual(result.clusters[0].touches, 2)
        self.assertIsNone(result.support)
        self.assertIsNone(result.resistance)

    def test_strict_swings_reject_equal_neighbors_and_flat_prices(self):
        values = candles(lows=(100,))
        values[3] = values[3].model_copy(update={"low": 100.0})
        self.assertEqual(detect_support_resistance(values).swings, ())
        self.assertEqual(detect_support_resistance(candles()).clusters, ())

    def test_confirmation_delay_and_custom_window(self):
        values = candles(lows=(100, 100), highs=(120, 120))
        early = detect_support_resistance(values[:8])
        self.assertEqual({point.index for point in early.swings}, {2})
        self.assertIsNone(early.support)
        confirmed = detect_support_resistance(values[:9])
        self.assertEqual({point.index for point in confirmed.swings}, {2, 6})
        self.assertEqual({point.confirmed_at_index for point in confirmed.swings}, {4, 8})
        self.assertIsNotNone(confirmed.support)
        custom = detect_support_resistance(values[:8], SupportResistancePolicy(swing_window=1))
        self.assertEqual({point.index for point in custom.swings}, {2, 6})

    def test_same_candle_counts_once_even_when_high_and_low_cluster(self):
        result = detect_support_resistance(candles(lows=(100,), highs=(120,)),
                                           SupportResistancePolicy(cluster_tolerance_pct=25))
        self.assertEqual(len(result.swings), 2)
        self.assertEqual(result.clusters[0].touches, 1)
        self.assertIsNone(result.support)
        self.assertIsNone(result.resistance)

    def test_insufficient_history_and_readiness(self):
        self.assertEqual(SUPPORT_RESISTANCE_POLICY.minimum_candles, 5)
        self.assertFalse(is_support_resistance_ready(4))
        self.assertTrue(is_support_resistance_ready(5))
        for size in (0, 1, 4):
            with self.subTest(size=size), self.assertRaises(InsufficientHistoryError) as caught:
                detect_support_resistance(candles(size=size))
            self.assertEqual((caught.exception.required, caught.exception.available), (5, size))
        self.assertIsNone(detect_support_resistance(candles(size=5)).support)
        policy = SupportResistancePolicy(swing_window=3)
        self.assertFalse(is_support_resistance_ready(6, policy))
        self.assertTrue(is_support_resistance_ready(7, policy))
        with self.assertRaises(InsufficientHistoryError):
            detect_support_resistance(candles(size=6), policy)

    def test_input_immutability_and_determinism(self):
        values = candles(lows=(100.5, 100), highs=(120, 120.5))
        original = [value.model_dump() for value in values]
        result = detect_support_resistance(values)
        self.assertEqual(result, detect_support_resistance(tuple(values)))
        self.assertEqual([value.model_dump() for value in values], original)
        with self.assertRaises(FrozenInstanceError):
            result.support.price = 0

    def test_invalid_candles_order_and_daily_duplicates(self):
        values = candles()
        for update in ({"high": 90}, {"low": 0}, {"close": float("nan")}, {"open": 200}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                detect_support_resistance([values[0].model_copy(update=update), *values[1:]])
        for invalid in (values[::-1], [values[0], *values],
                        [values[0].model_copy(update={"symbol": "MSFT"}), *values[1:]],
                        [values[0], values[1].model_copy(update={"timestamp": values[0].timestamp + timedelta(hours=1)}), *values[2:]]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                detect_support_resistance(invalid)
        with self.assertRaises(TypeError):
            detect_support_resistance([110] * 5)

    def test_policy_and_readiness_validation(self):
        for field in ("swing_window", "minimum_touches"):
            for value, error in ((0, ValueError), (-1, ValueError), (True, TypeError), (2.0, TypeError)):
                with self.subTest(field=field, value=value), self.assertRaises(error):
                    SupportResistancePolicy(**{field: value})
        for value, error in ((-1, ValueError), (float("nan"), ValueError), (float("inf"), ValueError),
                             (True, TypeError), ("1", TypeError)):
            with self.subTest(value=value), self.assertRaises(error):
                SupportResistancePolicy(cluster_tolerance_pct=value)
        for value, error in ((-1, ValueError), (True, TypeError), (5.0, TypeError)):
            with self.subTest(value=value), self.assertRaises(error):
                is_support_resistance_ready(value)
        with self.assertRaises(FrozenInstanceError):
            SUPPORT_RESISTANCE_POLICY.swing_window = 3


if __name__ == "__main__":
    unittest.main()
