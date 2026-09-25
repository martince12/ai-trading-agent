import unittest

from app.market_analysis.moving_averages import (
    InsufficientHistoryError, ema, ema20, ema50, sma, sma20, sma50,
)
from app.market_analysis.policy import Indicator, get_indicator_policy, is_indicator_ready


class MovingAverageTests(unittest.TestCase):
    def test_known_sma_values(self):
        self.assertEqual(sma([2, 4, 6, 8, 10], 3), [None, None, 4, 6, 8])

    def test_sma_uses_only_the_trailing_window(self):
        # Means of [2, 8], [8, 4], [4, 10], [10, 6].
        self.assertEqual(sma([2, 8, 4, 10, 6], 2), [None, 5, 6, 7, 8])

    def test_exact_first_ema_seed(self):
        # Seed is (2 + 4 + 6) / 3 = 4, not the first close (2).
        self.assertEqual(ema([2, 4, 6], 3), [None, None, 4])

    def test_subsequent_ema_values(self):
        # alpha=1/2: seed=4; 4+(10-4)/2=7; 7+(4-7)/2=5.5;
        # 5.5+(8-5.5)/2=6.75.
        self.assertEqual(ema([2, 4, 6, 10, 4, 8], 3), [None, None, 4, 7, 5.5, 6.75])

    def test_ema_with_another_configurable_period(self):
        # period=4, alpha=0.4: seed=5; next=7, 5.4, 6.84.
        actual = ema([2, 4, 6, 8, 10, 3, 9], 4)
        self.assertEqual(actual[:3], [None, None, None])
        for value, expected in zip(actual[3:], [5, 7, 5.4, 6.84], strict=True):
            self.assertAlmostEqual(value, expected)

    def _check_boundary(self, function, indicator, seed):
        minimum = get_indicator_policy(indicator).minimum_closes
        self.assertFalse(is_indicator_ready(indicator, minimum - 1))
        with self.assertRaises(InsufficientHistoryError) as caught:
            function(list(range(1, minimum)))
        self.assertEqual((caught.exception.required, caught.exception.available), (minimum, minimum - 1))
        self.assertTrue(is_indicator_ready(indicator, minimum))
        result = function(list(range(1, minimum + 1)))
        self.assertEqual(len(result), minimum)
        self.assertEqual(result[:-1], [None] * (minimum - 1))
        self.assertAlmostEqual(result[-1], seed)
        # For these linearly increasing closes, both SMA and SMA-seeded EMA advance by one.
        self.assertAlmostEqual(function(list(range(1, minimum + 2)))[-1], seed + 1)

    def test_sma20_readiness_boundary(self):
        self._check_boundary(sma20, Indicator.SMA20, 10.5)

    def test_sma50_readiness_boundary(self):
        self._check_boundary(sma50, Indicator.SMA50, 25.5)

    def test_ema20_readiness_boundary(self):
        self._check_boundary(ema20, Indicator.EMA20, 10.5)

    def test_ema50_readiness_boundary(self):
        self._check_boundary(ema50, Indicator.EMA50, 25.5)

    def test_insufficient_history_has_explicit_counts(self):
        for function in (sma, ema):
            for closes in ([], [2], [2, 4]):
                with self.subTest(function=function.__name__, closes=closes):
                    with self.assertRaises(InsufficientHistoryError) as caught:
                        function(closes, 3)
                    self.assertEqual(caught.exception.required, 3)
                    self.assertEqual(caught.exception.available, len(closes))
                    self.assertIn("requires 3 closes", str(caught.exception))

    def test_inputs_are_not_mutated_and_results_are_independent(self):
        closes = list(range(1, 61))
        original = closes.copy()
        for function in (sma20, sma50, ema20, ema50):
            with self.subTest(function=function.__name__):
                result = function(closes)
                self.assertEqual(closes, original)
                self.assertIsNot(result, closes)
                self.assertEqual(result, function(tuple(closes)))
                result[-1] = -1
                self.assertEqual(closes, original)
        for function in (sma, ema):
            with self.assertRaises(InsufficientHistoryError):
                function(closes, 61)
            self.assertEqual(closes, original)

    def test_period_one_returns_each_close(self):
        for function in (sma, ema):
            self.assertEqual(function([3, 1, 8], 1), [3, 1, 8])

    def test_invalid_periods_are_rejected(self):
        for function in (sma, ema):
            for period, error in ((0, ValueError), (-1, ValueError), (True, TypeError),
                                  (2.0, TypeError), ("2", TypeError), (None, TypeError)):
                with self.subTest(function=function.__name__, period=period):
                    with self.assertRaises(error):
                        function([1, 2, 3], period)

    def test_invalid_closes_are_rejected_even_after_seed(self):
        for function in (sma, ema):
            for value, error in ((0, ValueError), (-1, ValueError), (float("nan"), ValueError),
                                 (float("inf"), ValueError), (float("-inf"), ValueError),
                                 (True, TypeError), ("4", TypeError), (None, TypeError)):
                with self.subTest(function=function.__name__, value=value):
                    with self.assertRaises(error):
                        function([1, 2, 3, value], 3)
            with self.assertRaises(TypeError):
                function("123", 2)

    def test_large_finite_closes_do_not_overflow_the_mean(self):
        for function in (sma, ema):
            result = function([9e307] * 5, 3)
            self.assertEqual(result[:2], [None, None])
            for value in result[2:]:
                self.assertAlmostEqual(value / 9e307, 1)


if __name__ == "__main__":
    unittest.main()
