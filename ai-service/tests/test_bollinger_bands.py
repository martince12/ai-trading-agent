import unittest

from app.market_analysis.bollinger_bands import bollinger_bands, bollinger_bands_20_2
from app.market_analysis.moving_averages import InsufficientHistoryError, sma, sma20
from app.market_analysis.policy import Indicator, get_indicator_policy, is_indicator_ready


class BollingerBandsTests(unittest.TestCase):
    def test_manually_verifiable_rolling_sequence(self):
        # Windows [1,3], [3,7], [7,5]: means 2,5,6; population deviations 1,2,1.
        result = bollinger_bands([1, 3, 7, 5], 2, 2)
        self.assertEqual(result.middle, [None, 2, 5, 6])
        self.assertEqual(result.upper, [None, 4, 9, 8])
        self.assertEqual(result.lower, [None, 0, 1, 4])

    def test_exact_middle_sma(self):
        closes = [2, 4, 4, 4, 5, 5, 7, 9]
        result = bollinger_bands(closes, 8, 2)
        self.assertEqual(result.middle, sma(closes, 8))
        self.assertEqual(result.middle[-1], 5)

    def test_exact_population_standard_deviation(self):
        # Mean=5, squared deviations sum=32. Population variance=32/8=4, SD=2.
        # A sample SD would be sqrt(32/7), so it would fail this assertion.
        result = bollinger_bands([2, 4, 4, 4, 5, 5, 7, 9], 8, 1)
        self.assertEqual(result.upper[-1] - result.middle[-1], 2)
        self.assertEqual(result.middle[-1] - result.lower[-1], 2)

    def test_upper_lower_and_configurable_multiplier(self):
        closes = [2, 4, 4, 4, 5, 5, 7, 9]
        for multiplier, upper, lower in ((2, 9, 1), (0.5, 6, 4), (3, 11, -1)):
            with self.subTest(multiplier=multiplier):
                result = bollinger_bands(closes, 8, multiplier)
                self.assertEqual(result.upper[-1], upper)
                self.assertEqual(result.lower[-1], lower)

    def test_standard_19_20_boundary(self):
        indicator = Indicator.BOLLINGER_BANDS_20_2
        self.assertFalse(is_indicator_ready(indicator, 19))
        with self.assertRaises(InsufficientHistoryError) as caught:
            bollinger_bands_20_2(list(range(1, 20)))
        self.assertEqual((caught.exception.required, caught.exception.available), (20, 19))
        self.assertTrue(is_indicator_ready(indicator, 20))
        result = bollinger_bands_20_2(list(range(1, 21)))
        for series in (result.middle, result.upper, result.lower):
            self.assertEqual(len(series), 20)
            self.assertEqual(series[:19], [None] * 19)
            self.assertIsNotNone(series[19])
        self.assertEqual(result.middle[19], 10.5)
        # Population variance for 1..20 is (20^2 - 1)/12 = 33.25.
        self.assertAlmostEqual(result.upper[19], 10.5 + 2 * 33.25 ** 0.5)
        self.assertAlmostEqual(result.lower[19], 10.5 - 2 * 33.25 ** 0.5)

    def test_standard_uses_policy_and_existing_sma20(self):
        policy = get_indicator_policy(Indicator.BOLLINGER_BANDS_20_2)
        closes = [2, 4, 6, 10, 4, 8] * 5
        result = bollinger_bands_20_2(closes)
        self.assertEqual(policy.ddof, 0)
        self.assertEqual(result, bollinger_bands(closes, policy.center.period, policy.standard_deviation_multiplier))
        self.assertEqual(result.middle, sma20(closes))

    def test_flat_prices_all_bands_coincide(self):
        for price in (10, 0.1, 9e307):
            with self.subTest(price=price):
                result = bollinger_bands_20_2([price] * 25)
                self.assertEqual(result.upper, result.middle)
                self.assertEqual(result.lower, result.middle)
                self.assertEqual(result.middle[:19], [None] * 19)
                for value in result.middle[19:]:
                    self.assertAlmostEqual(value / price, 1)

    def test_insufficient_history(self):
        for closes in ([], [2], [2, 4]):
            with self.subTest(closes=closes), self.assertRaises(InsufficientHistoryError) as caught:
                bollinger_bands(closes, 3, 2)
            self.assertEqual((caught.exception.required, caught.exception.available), (3, len(closes)))
        with self.assertRaises(InsufficientHistoryError) as caught:
            bollinger_bands_20_2([])
        self.assertEqual(caught.exception.required, 20)

    def test_result_alignment(self):
        result = bollinger_bands([2, 4, 6, 8, 10, 12], 3, 2)
        for series in (result.middle, result.upper, result.lower):
            self.assertEqual(len(series), 6)
            self.assertEqual(series[:2], [None, None])
            self.assertTrue(all(value is not None for value in series[2:]))
        self.assertEqual(result.middle[2:], [4, 6, 8, 10])

    def test_input_immutability_and_independent_results(self):
        closes = list(range(1, 31))
        original = closes.copy()
        for calculate in (lambda values: bollinger_bands(values, 3, 2), bollinger_bands_20_2):
            result = calculate(closes)
            self.assertEqual(closes, original)
            self.assertEqual(result, calculate(tuple(closes)))
            upper, lower = result.upper.copy(), result.lower.copy()
            result.middle[-1] = -999
            self.assertEqual(result.upper, upper)
            self.assertEqual(result.lower, lower)
            self.assertEqual(closes, original)
        with self.assertRaises(InsufficientHistoryError):
            bollinger_bands(closes, 31, 2)
        self.assertEqual(closes, original)

    def test_period_one_and_zero_multiplier(self):
        closes = [2, 8, 4, 10]
        result = bollinger_bands(closes, 1, 2)
        self.assertEqual(result.middle, closes)
        self.assertEqual(result.upper, closes)
        self.assertEqual(result.lower, closes)
        zero = bollinger_bands(closes, 2, 0)
        self.assertEqual(zero.upper, zero.middle)
        self.assertEqual(zero.lower, zero.middle)

    def test_invalid_periods(self):
        for period, error in ((0, ValueError), (-1, ValueError), (True, TypeError),
                              (2.0, TypeError), ("2", TypeError), (None, TypeError)):
            with self.subTest(period=period), self.assertRaises(error):
                bollinger_bands([1, 2, 3], period, 2)

    def test_invalid_multipliers(self):
        for multiplier, error in ((-1, ValueError), (float("nan"), ValueError),
                                  (float("inf"), ValueError), (True, TypeError),
                                  ("2", TypeError), (None, TypeError), (10**400, ValueError)):
            with self.subTest(multiplier=multiplier), self.assertRaises(error):
                bollinger_bands([1, 2, 3], 2, multiplier)

    def test_invalid_closes_even_after_first_window(self):
        for value, error in ((0, ValueError), (-1, ValueError), (float("nan"), ValueError),
                             (float("inf"), ValueError), (True, TypeError), ("4", TypeError),
                             (None, TypeError)):
            with self.subTest(value=value), self.assertRaises(error):
                bollinger_bands([1, 2, 3, value], 2, 2)
        with self.assertRaises(TypeError):
            bollinger_bands("123", 2, 2)

    def test_unrepresentable_bands_raise_instead_of_returning_infinity(self):
        with self.assertRaises(ValueError):
            bollinger_bands([1, 9], 2, 1e308)


if __name__ == "__main__":
    unittest.main()
