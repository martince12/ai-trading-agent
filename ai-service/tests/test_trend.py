import unittest
from dataclasses import FrozenInstanceError, astuple
from unittest.mock import patch

from app.market_analysis.macd import MacdResult
from app.market_analysis.moving_averages import InsufficientHistoryError, ema20, ema50
from app.market_analysis.policy import TREND_POLICY, is_trend_ready
from app.market_analysis.trend import TrendState, detect_trend, latest_trend


class TrendTests(unittest.TestCase):
    def test_clearly_bullish_sequence(self):
        result = latest_trend([100 + i * i for i in range(80)])
        self.assertEqual(result.state, TrendState.BULLISH)
        self.assertEqual(result.score, 6)
        self.assertEqual(astuple(result.signals), (1, 1, 1, 1, 1, 1))

    def test_clearly_bearish_sequence(self):
        result = latest_trend([10000 - i * i for i in range(80)])
        self.assertEqual(result.state, TrendState.BEARISH)
        self.assertEqual(result.score, -6)
        self.assertEqual(astuple(result.signals), (-1, -1, -1, -1, -1, -1))

    def test_mixed_neutral_sequence(self):
        result = latest_trend([100 + i for i in range(60)] + [159 - i for i in range(10)])
        self.assertEqual(result.state, TrendState.NEUTRAL)
        self.assertEqual(result.score, 0)
        self.assertEqual(astuple(result.signals), (-1, 1, -1, 1, -1, 1))

    def test_exact_thresholds_and_neutral_neighbors(self):
        # Controlled indicator outputs isolate scoring; EMA slopes still use real ROC.
        for current, old, expected, state in (
            (15, 5, 3, TrendState.BULLISH), (5, 20, -3, TrendState.BEARISH),
            (10, 5, 2, TrendState.NEUTRAL), (10, 20, -2, TrendState.NEUTRAL),
        ):
            with self.subTest(score=expected):
                fast = [None] * 19 + [10.0] * 36
                slow = [None] * 49 + [10.0] * 6
                fast[49] = slow[49] = old
                with (patch("app.market_analysis.trend.ema20", return_value=fast),
                      patch("app.market_analysis.trend.ema50", return_value=slow),
                      patch("app.market_analysis.trend.macd_12_26_9", return_value=MacdResult(
                          [None] * 25 + [0.0] * 30, [None] * 33 + [0.0] * 22, [None] * 33 + [0.0] * 22)),
                      patch("app.market_analysis.trend.momentum20", return_value=[None] * 20 + [0.0] * 35)):
                    result = latest_trend([10.0] * 54 + [current])
                self.assertEqual(result.score, expected)
                self.assertEqual(result.state, state)
                self.assertEqual(result.signals.ema20_vs_ema50, 0)
                self.assertEqual(result.signals.macd_histogram, 0)
                self.assertEqual(result.signals.momentum20, 0)

    def test_equality_gives_zero_for_every_component(self):
        result = latest_trend([100] * 80)
        self.assertEqual(result.state, TrendState.NEUTRAL)
        self.assertEqual(result.score, 0)
        self.assertEqual(astuple(result.signals), (0, 0, 0, 0, 0, 0))
        self.assertEqual((result.ema20_slope_pct, result.ema50_slope_pct), (0, 0))

    def test_positive_ema_slopes(self):
        # With closes 1..55, SMA-seeded EMAs follow the line exactly.
        # EMA20 at t54/t49 = 45.5/40.5; EMA50 = 30.5/25.5.
        result = latest_trend(list(range(1, 56)))
        self.assertAlmostEqual(result.ema20_slope_pct, (45.5 / 40.5 - 1) * 100)
        self.assertAlmostEqual(result.ema50_slope_pct, (30.5 / 25.5 - 1) * 100)
        self.assertEqual((result.signals.ema20_slope, result.signals.ema50_slope), (1, 1))

    def test_negative_ema_slopes(self):
        # With closes 100..46, EMA20 = 55.5/60.5; EMA50 = 70.5/75.5.
        result = latest_trend(list(range(100, 45, -1)))
        self.assertAlmostEqual(result.ema20_slope_pct, (55.5 / 60.5 - 1) * 100)
        self.assertAlmostEqual(result.ema50_slope_pct, (70.5 / 75.5 - 1) * 100)
        self.assertEqual((result.signals.ema20_slope, result.signals.ema50_slope), (-1, -1))

    def test_54_55_close_boundary_and_alignment(self):
        self.assertEqual(TREND_POLICY.minimum_closes, 55)
        self.assertFalse(is_trend_ready(54))
        with self.assertRaises(InsufficientHistoryError) as caught:
            detect_trend([100] * 54)
        self.assertEqual((caught.exception.required, caught.exception.available), (55, 54))
        self.assertTrue(is_trend_ready(55))
        self.assertIsNotNone(detect_trend([100] * 55)[54])
        results = detect_trend([100] * 60)
        self.assertEqual(len(results), 60)
        self.assertEqual(results[:54], [None] * 54)
        self.assertTrue(all(result is not None for result in results[54:]))

    def test_insufficient_history_for_both_apis(self):
        for calculate in (detect_trend, latest_trend):
            for size in (0, 20, 50, 54):
                with self.subTest(calculate=calculate.__name__, size=size), self.assertRaises(InsufficientHistoryError) as caught:
                    calculate([100] * size)
                self.assertEqual((caught.exception.required, caught.exception.available), (55, size))

    def test_input_immutability_and_determinism(self):
        closes = [100 + i * i for i in range(70)]
        original = closes.copy()
        results = detect_trend(closes)
        self.assertEqual(results, detect_trend(tuple(closes)))
        self.assertEqual(results[-1], latest_trend(closes))
        self.assertEqual(closes, original)
        with self.assertRaises(FrozenInstanceError):
            results[-1].score = 0
        with self.assertRaises(FrozenInstanceError):
            results[-1].signals.macd_histogram = 0

    def test_no_lookahead_from_later_closes(self):
        closes = [100 + i * i for i in range(80)]
        self.assertEqual(detect_trend(closes)[:60], detect_trend(closes[:60]))

    def test_existing_indicator_functions_are_reused(self):
        from app.market_analysis.macd import macd_12_26_9
        from app.market_analysis.momentum import momentum20
        with (patch("app.market_analysis.trend.ema20", wraps=ema20) as fast,
              patch("app.market_analysis.trend.ema50", wraps=ema50) as slow,
              patch("app.market_analysis.trend.macd_12_26_9", wraps=macd_12_26_9) as macd,
              patch("app.market_analysis.trend.momentum20", wraps=momentum20) as mom):
            latest_trend([100] * 60)
            for function in (fast, slow, macd, mom):
                function.assert_called_once()

    def test_invalid_inputs_and_counts(self):
        for value, error in ((0, ValueError), (-1, ValueError), (float("nan"), ValueError),
                             (float("inf"), ValueError), (True, TypeError), ("100", TypeError)):
            with self.subTest(value=value), self.assertRaises(error):
                latest_trend([100] * 55 + [value])
        for count, error in ((-1, ValueError), (True, TypeError), (55.0, TypeError), ("55", TypeError)):
            with self.subTest(count=count), self.assertRaises(error):
                is_trend_ready(count)

    def test_trend_policy_is_immutable(self):
        self.assertEqual(TREND_POLICY.slope_lookback, 5)
        self.assertEqual((TREND_POLICY.bullish_threshold, TREND_POLICY.bearish_threshold), (3, -3))
        with self.assertRaises(FrozenInstanceError):
            TREND_POLICY.slope_lookback = 10


if __name__ == "__main__":
    unittest.main()
