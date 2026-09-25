import unittest
from dataclasses import FrozenInstanceError

from app.market_analysis.moving_averages import InsufficientHistoryError
from app.market_analysis.policy import VOLUME_POLICY, is_volume_ready
from app.market_analysis.volume import average_volume, average_volume20, analyze_volume20


class VolumeTests(unittest.TestCase):
    def test_manual_trailing_average(self):
        self.assertEqual(average_volume([0, 3, 6, 3], 3), [None, None, 3, 4])

    def test_exact_ratio_and_percentage_above_average(self):
        # Nineteen 10s + 30 -> mean 11, current/mean=30/11.
        result = analyze_volume20([10] * 19 + [30])
        self.assertEqual(result.average_volume_20[-1], 11)
        self.assertEqual(result.volume_ratio[-1], 30 / 11)
        self.assertEqual(result.volume_vs_average_pct[-1], (30 / 11 - 1) * 100)

    def test_exact_percentage_below_average(self):
        # Nineteen 21s + 1 -> mean 20, ratio 0.05, percentage -95.
        result = analyze_volume20([21] * 19 + [1])
        self.assertEqual(result.average_volume_20[-1], 20)
        self.assertEqual(result.volume_ratio[-1], 0.05)
        self.assertEqual(result.volume_vs_average_pct[-1], -95)

    def test_current_volume_is_included(self):
        result = analyze_volume20([0] * 19 + [20])
        self.assertEqual(result.average_volume_20[-1], 1)
        self.assertEqual(result.volume_ratio[-1], 20)
        self.assertEqual(result.volume_vs_average_pct[-1], 1900)

    def test_19_20_boundary_and_standard_average(self):
        self.assertEqual(VOLUME_POLICY.minimum_values, 20)
        self.assertFalse(is_volume_ready(19))
        for calculate in (average_volume20, analyze_volume20):
            with self.assertRaises(InsufficientHistoryError) as caught:
                calculate([10] * 19)
            self.assertEqual((caught.exception.required, caught.exception.available), (20, 19))
        self.assertTrue(is_volume_ready(20))
        values = list(range(1, 21))
        self.assertEqual(average_volume20(values), [None] * 19 + [10.5])
        self.assertEqual(average_volume20(values), average_volume(values, VOLUME_POLICY.period))

    def test_constant_volume(self):
        result = analyze_volume20([10] * 23)
        self.assertEqual(result.average_volume_20, [None] * 19 + [10] * 4)
        self.assertEqual(result.volume_ratio, [None] * 19 + [1] * 4)
        self.assertEqual(result.volume_vs_average_pct, [None] * 19 + [0] * 4)

    def test_zero_average_and_recovery(self):
        result = analyze_volume20([0] * 21 + [20])
        self.assertEqual(result.average_volume_20, [None] * 19 + [0, 0, 1])
        self.assertEqual(result.volume_ratio, [None] * 21 + [20])
        self.assertEqual(result.volume_vs_average_pct, [None] * 21 + [1900])

    def test_zero_current_volume_with_positive_average(self):
        result = analyze_volume20([20] * 19 + [0])
        self.assertEqual(result.average_volume_20[-1], 19)
        self.assertEqual(result.volume_ratio[-1], 0)
        self.assertEqual(result.volume_vs_average_pct[-1], -100)

    def test_fractional_volume_and_period_one(self):
        self.assertEqual(average_volume([0.5, 1.5, 0], 2), [None, 1, 0.75])
        self.assertEqual(average_volume([0, 3.5, 1], 1), [0, 3.5, 1])

    def test_insufficient_history(self):
        for volumes in ([], [0], [0, 1]):
            with self.subTest(volumes=volumes), self.assertRaises(InsufficientHistoryError) as caught:
                average_volume(volumes, 3)
            self.assertEqual((caught.exception.required, caught.exception.available), (3, len(volumes)))
            self.assertIn("3 volume values", str(caught.exception))

    def test_alignment_and_trailing_window(self):
        volumes = [100] + [20] * 20 + [40]
        result = analyze_volume20(volumes)
        for series in (result.average_volume_20, result.volume_ratio, result.volume_vs_average_pct):
            self.assertEqual(len(series), len(volumes))
            self.assertEqual(series[:19], [None] * 19)
            self.assertTrue(all(value is not None for value in series[19:]))
        self.assertEqual(result.average_volume_20[19:], [24, 20, 21])

    def test_input_immutability_and_independent_lists(self):
        volumes = list(range(30))
        original = volumes.copy()
        result = analyze_volume20(volumes)
        self.assertEqual(result, analyze_volume20(tuple(volumes)))
        averages, percentages = result.average_volume_20.copy(), result.volume_vs_average_pct.copy()
        result.volume_ratio[-1] = -999
        self.assertEqual(result.average_volume_20, averages)
        self.assertEqual(result.volume_vs_average_pct, percentages)
        self.assertEqual(volumes, original)
        average_volume(volumes, 3)[-1] = -999
        with self.assertRaises(InsufficientHistoryError):
            average_volume(volumes, 31)
        self.assertEqual(volumes, original)

    def test_invalid_volumes_even_after_initial_window(self):
        for value, error in ((-1, ValueError), (float("nan"), ValueError), (float("inf"), ValueError),
                             (1e308, ValueError), (10**400, ValueError), (True, TypeError),
                             ("1", TypeError), (None, TypeError)):
            with self.subTest(value=value), self.assertRaises(error):
                analyze_volume20([1] * 20 + [value])
        with self.assertRaises(TypeError):
            average_volume("123", 2)

    def test_invalid_periods_and_readiness_counts(self):
        for value, error in ((-1, ValueError), (True, TypeError), (2.0, TypeError), ("2", TypeError)):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    average_volume([1, 2, 3], value)
                with self.assertRaises(error):
                    is_volume_ready(value)
        with self.assertRaises(ValueError):
            average_volume([1, 2], 0)
        self.assertFalse(is_volume_ready(0))

    def test_volume_policy_is_immutable(self):
        self.assertTrue(VOLUME_POLICY.include_current)
        self.assertIsNone(VOLUME_POLICY.zero_average_ratio)
        with self.assertRaises(FrozenInstanceError):
            VOLUME_POLICY.period = 50

    def test_large_finite_volume_does_not_overflow(self):
        result = analyze_volume20([9e307] * 21)
        for index in (19, 20):
            self.assertAlmostEqual(result.average_volume_20[index] / 9e307, 1)
            self.assertAlmostEqual(result.volume_ratio[index], 1)
            self.assertAlmostEqual(result.volume_vs_average_pct[index], 0)


if __name__ == "__main__":
    unittest.main()
