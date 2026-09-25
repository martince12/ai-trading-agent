import unittest

from app.market_analysis.macd import macd, macd_12_26_9
from app.market_analysis.moving_averages import InsufficientHistoryError, ema
from app.market_analysis.policy import Indicator, get_indicator_policy, is_indicator_ready


class MacdTests(unittest.TestCase):
    CLOSES = [2, 4, 6, 10, 4, 8, 12, 6]

    def assert_series(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for index, (value, reference) in enumerate(zip(actual, expected, strict=True)):
            with self.subTest(index=index):
                if reference is None:
                    self.assertIsNone(value)
                else:
                    self.assertAlmostEqual(value, reference)

    def test_manually_verifiable_macd_line(self):
        # EMA2 starts at 3, EMA3 at 4. At index 2 fast=5, slow=4.
        # Next fast/slow pairs: 25/3 and 7; 49/9 and 11/2;
        # 193/27 and 27/4; 841/81 and 75/8; 1813/243 and 123/16.
        result = macd(self.CLOSES, 2, 3, 2)
        self.assert_series(result.macd, [None, None, 1, 4/3, -1/18, 43/108, 653/648, -881/3888])

    def test_first_valid_standard_macd_line(self):
        result = macd_12_26_9(list(range(1, 35)))
        self.assertEqual(result.macd[:25], [None] * 25)
        # At close 26, EMA12=20.5 and EMA26=13.5, giving MACD=7.
        self.assertAlmostEqual(result.macd[25], 7)

    def test_signal_seed_is_exact_mean_of_first_available_values(self):
        # EMA1 = price. First EMA3=4, next=7; first MACDs=2,3.
        result = macd([2, 4, 6, 10], 1, 3, 2)
        self.assertEqual(result.macd, [None, None, 2, 3])
        self.assertEqual(result.signal, [None, None, None, 2.5])
        self.assertEqual(result.histogram, [None, None, None, 0.5])

    def test_subsequent_signal_ema_values(self):
        # Signal seed=(1+4/3)/2=7/6; alpha=2/3.
        # At the next step: 7/6 + (2/3)*(-1/18-7/6) = 19/54.
        result = macd(self.CLOSES, 2, 3, 2)
        self.assert_series(result.signal, [None, None, None, 7/6, 19/54, 31/81, 259/324, 673/5832])

    def test_histogram_manual_values(self):
        result = macd(self.CLOSES, 2, 3, 2)
        self.assert_series(result.histogram, [None, None, None, 1/6, -11/27, 5/324, 5/24, -3989/11664])

    def test_standard_33_34_close_boundary(self):
        self.assertFalse(is_indicator_ready(Indicator.MACD_12_26_9, 33))
        with self.assertRaises(InsufficientHistoryError) as caught:
            macd_12_26_9(list(range(1, 34)))
        self.assertEqual((caught.exception.required, caught.exception.available), (34, 33))
        self.assertTrue(is_indicator_ready(Indicator.MACD_12_26_9, 34))
        result = macd_12_26_9(list(range(1, 35)))
        self.assertEqual(result.signal[:33], [None] * 33)
        self.assertEqual(result.histogram[:33], [None] * 33)
        self.assertAlmostEqual(result.signal[33], 7)
        self.assertAlmostEqual(result.histogram[33], 0)

    def test_standard_function_uses_policy_parameters(self):
        policy = get_indicator_policy(Indicator.MACD_12_26_9)
        closes = self.CLOSES * 6
        self.assertEqual(macd_12_26_9(closes), macd(
            closes, policy.fast.period, policy.slow.period, policy.signal.period,
        ))

    def test_insufficient_history_reports_complete_requirement(self):
        for closes in ([], [2], [2, 4, 6]):
            with self.subTest(closes=closes), self.assertRaises(InsufficientHistoryError) as caught:
                macd(closes, 2, 3, 2)
            self.assertEqual((caught.exception.required, caught.exception.available), (4, len(closes)))
        # Having a MACD line alone does not satisfy complete-output readiness.
        with self.assertRaises(InsufficientHistoryError) as caught:
            macd_12_26_9(list(range(1, 27)))
        self.assertEqual((caught.exception.required, caught.exception.available), (34, 26))

    def test_alignment_with_configurable_signal_period(self):
        result = macd(self.CLOSES, 2, 3, 3)
        for series, start in ((result.macd, 2), (result.signal, 4), (result.histogram, 4)):
            self.assertEqual(len(series), len(self.CLOSES))
            self.assertEqual(series[:start], [None] * start)
            self.assertTrue(all(value is not None for value in series[start:]))

    def test_input_immutability_and_independent_results(self):
        closes = self.CLOSES * 6
        original = closes.copy()
        for calculate in (lambda values: macd(values, 2, 3, 2), macd_12_26_9):
            result = calculate(closes)
            self.assertEqual(closes, original)
            self.assertEqual(result, calculate(tuple(closes)))
            unchanged_signal = result.signal.copy()
            unchanged_histogram = result.histogram.copy()
            result.macd[-1] = -999
            self.assertEqual(result.signal, unchanged_signal)
            self.assertEqual(result.histogram, unchanged_histogram)
            self.assertEqual(closes, original)
        with self.assertRaises(InsufficientHistoryError):
            macd(closes, 2, 3, len(closes))
        self.assertEqual(closes, original)

    def test_flat_prices_allow_zero_macd_and_signal(self):
        result = macd_12_26_9([10] * 40)
        self.assert_series(result.macd, [None] * 25 + [0] * 15)
        self.assert_series(result.signal, [None] * 33 + [0] * 7)
        self.assert_series(result.histogram, [None] * 33 + [0] * 7)

    def test_negative_signal_values_are_valid_but_negative_closes_are_not(self):
        result = macd(list(range(10, 0, -1)), 2, 3, 2)
        self.assert_series(result.macd, [None] * 2 + [-0.5] * 8)
        self.assert_series(result.signal, [None] * 3 + [-0.5] * 7)
        self.assert_series(result.histogram, [None] * 3 + [0] * 7)
        with self.assertRaises(ValueError):
            ema([1, 2, -1, 3], 2)

    def test_period_one_equal_and_reversed_periods(self):
        result = macd(self.CLOSES, 2, 3, 1)
        self.assertEqual(result.signal, result.macd)
        self.assert_series(result.histogram, [None] * 2 + [0] * 6)
        equal = macd(self.CLOSES, 2, 2, 2)
        self.assert_series(equal.macd, [None] + [0] * 7)
        reversed_result = macd(self.CLOSES, 3, 2, 2)
        normal = macd(self.CLOSES, 2, 3, 2)
        self.assert_series(reversed_result.macd, [None if value is None else -value for value in normal.macd])

    def test_invalid_periods(self):
        for position in range(3):
            for value, error in ((0, ValueError), (-1, ValueError), (True, TypeError),
                                 (2.0, TypeError), ("2", TypeError), (None, TypeError)):
                periods = [2, 3, 2]
                periods[position] = value
                with self.subTest(position=position, value=value), self.assertRaises(error):
                    macd(self.CLOSES, *periods)

    def test_invalid_closes_are_rejected_even_after_seed(self):
        for value, error in ((0, ValueError), (-1, ValueError), (float("nan"), ValueError),
                             (float("inf"), ValueError), (True, TypeError), ("4", TypeError),
                             (None, TypeError)):
            with self.subTest(value=value), self.assertRaises(error):
                macd([2, 4, 6, 10, value], 2, 3, 2)
        with self.assertRaises(TypeError):
            macd("2468", 2, 3, 2)


if __name__ == "__main__":
    unittest.main()
