import unittest

from app.market_analysis.moving_averages import InsufficientHistoryError
from app.market_analysis.policy import Indicator, get_indicator_policy, is_indicator_ready
from app.market_analysis.rsi import rsi, rsi14


class RsiTests(unittest.TestCase):
    def test_initial_rsi_from_manual_changes(self):
        # Changes +2, -1, +2: gain=4/3, loss=1/3, RS=4, RSI=80.
        self.assertEqual(rsi([10, 12, 11, 13], 3), [None, None, None, 80.0])

    def test_several_wilder_smoothed_values(self):
        # Seed: gain=4/3, loss=1/3.
        # -1: gain=8/9, loss=5/9 -> RSI=800/13.
        # +3: gain=43/27, loss=10/27 -> RSI=4300/53.
        # -2: gain=86/81, loss=74/81 -> RSI=53.75.
        #  0: both decay by 2/3, RSI remains 53.75.
        actual = rsi([10, 12, 11, 13, 12, 15, 13, 13], 3)
        self.assertEqual(actual[:3], [None, None, None])
        for value, expected in zip(actual[3:], [80, 800 / 13, 4300 / 53, 53.75, 53.75], strict=True):
            self.assertAlmostEqual(value, expected)

    def test_unchanged_prices_are_included_in_initial_averages(self):
        # Changes +2, 0, -1: initial means 2/3 and 1/3, then +1
        # gives means 7/9 and 2/9. Omitting the zero change alters smoothing.
        values = rsi([10, 12, 12, 11, 12], 3)
        self.assertAlmostEqual(values[3], 200 / 3)
        self.assertAlmostEqual(values[4], 700 / 9)

    def test_rsi14_readiness_and_mixed_initial_seed(self):
        policy = get_indicator_policy(Indicator.RSI14)
        closes = [10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17, 16, 18, 17]
        self.assertEqual(policy.minimum_closes, 15)
        self.assertFalse(is_indicator_ready(Indicator.RSI14, 14))
        with self.assertRaises(InsufficientHistoryError) as caught:
            rsi14(closes[:14])
        self.assertEqual((caught.exception.required, caught.exception.available), (15, 14))
        self.assertTrue(is_indicator_ready(Indicator.RSI14, 15))
        result = rsi14(closes)
        self.assertEqual(result[:14], [None] * 14)
        self.assertEqual(len(result), 15)
        # Seven +2 changes and seven -1 changes: gain=1, loss=1/2, RS=2.
        self.assertAlmostEqual(result[14], 200 / 3)
        self.assertEqual(result, rsi(closes, policy.period))

    def test_all_gains(self):
        self.assertEqual(rsi14(list(range(1, 21))), [None] * 14 + [100.0] * 6)

    def test_all_losses(self):
        self.assertEqual(rsi14(list(range(20, 0, -1))), [None] * 14 + [0.0] * 6)

    def test_flat_prices_return_policy_neutral_value(self):
        self.assertEqual(get_indicator_policy(Indicator.RSI14).flat_market_value, 50)
        self.assertEqual(rsi14([10] * 20), [None] * 14 + [50.0] * 6)

    def test_transitions_from_flat_seed(self):
        self.assertEqual(rsi([10, 10, 10, 12, 12], 2), [None, None, 50, 100, 100])
        self.assertEqual(rsi([10, 10, 10, 8, 8], 2), [None, None, 50, 0, 0])

    def test_period_one(self):
        self.assertEqual(rsi([10, 12, 11, 11, 13], 1), [None, 100, 0, 50, 100])

    def test_insufficient_history_uses_shared_exception(self):
        for closes in ([], [10], [10, 11], [10, 11, 12]):
            with self.subTest(closes=closes), self.assertRaises(InsufficientHistoryError) as caught:
                rsi(closes, 3)
            self.assertEqual(caught.exception.required, 4)
            self.assertEqual(caught.exception.available, len(closes))
            self.assertIn("requires 4 closes", str(caught.exception))
        with self.assertRaises(InsufficientHistoryError) as caught:
            rsi14([])
        self.assertEqual(caught.exception.required, 15)

    def test_input_immutability_and_alignment(self):
        closes = [10, 12, 11, 13, 12, 15, 13, 13] * 3
        original = closes.copy()
        for calculate in (lambda values: rsi(values, 3), rsi14):
            result = calculate(closes)
            self.assertEqual(closes, original)
            self.assertEqual(len(result), len(closes))
            self.assertEqual(result, calculate(tuple(closes)))
            result[-1] = -1
            self.assertEqual(closes, original)
        with self.assertRaises(InsufficientHistoryError):
            rsi(closes, len(closes))
        self.assertEqual(closes, original)

    def test_invalid_periods_follow_shared_conventions(self):
        for period, error in ((0, ValueError), (-1, ValueError), (True, TypeError),
                              (2.0, TypeError), ("2", TypeError), (None, TypeError)):
            with self.subTest(period=period), self.assertRaises(error):
                rsi([10, 11, 12, 13], period)

    def test_invalid_closes_even_after_seed_are_rejected(self):
        for value, error in ((0, ValueError), (-1, ValueError), (float("nan"), ValueError),
                             (float("inf"), ValueError), (True, TypeError), ("10", TypeError),
                             (None, TypeError)):
            with self.subTest(value=value), self.assertRaises(error):
                rsi([10, 11, 12, 13, value], 3)
        with self.assertRaises(TypeError):
            rsi("1234", 3)

    def test_large_finite_prices_keep_smoothing_finite(self):
        # Scaling all closes must leave these ratios unchanged.
        closes = [1, 9, 8, 16, 8, 9, 1, 9, 9]
        expected = rsi(closes, 3)
        actual = rsi([value * 1e307 for value in closes], 3)
        for value, reference in zip(actual[3:], expected[3:], strict=True):
            self.assertAlmostEqual(value, reference)
            self.assertTrue(0 <= value <= 100)


if __name__ == "__main__":
    unittest.main()
