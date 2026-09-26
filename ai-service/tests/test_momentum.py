import unittest
from dataclasses import FrozenInstanceError

from app.market_analysis.momentum import momentum, momentum10, momentum20
from app.market_analysis.moving_averages import InsufficientHistoryError
from app.market_analysis.policy import (
    MOMENTUM10_POLICY, MOMENTUM20_POLICY, is_momentum10_ready, is_momentum20_ready,
)


class MomentumTests(unittest.TestCase):
    def test_manual_positive_momentum(self):
        self.assertEqual(momentum([100, 125], 1), [None, 25])

    def test_manual_negative_momentum(self):
        self.assertEqual(momentum([100, 75], 1), [None, -25])

    def test_zero_momentum_for_equal_endpoint_prices(self):
        self.assertEqual(momentum([10, 20, 10, 20], 2), [None, None, 0, 0])
        self.assertEqual(momentum20([10] * 23), [None] * 20 + [0] * 3)

    def test_generic_lookback_uses_correct_prior_close(self):
        # 125/100, 100/80, 250/125: endpoint changes, not daily-return sums.
        self.assertEqual(momentum([100, 80, 125, 100, 250], 2), [None, None, 25, 25, 100])

    def test_exact_standard_10_day_value(self):
        closes = [100] * 10 + [125]
        self.assertEqual(momentum10(closes), [None] * 10 + [25])
        self.assertEqual(momentum10(closes), momentum(closes, MOMENTUM10_POLICY.period))

    def test_exact_standard_20_day_value(self):
        closes = [100] * 20 + [50]
        self.assertEqual(momentum20(closes), [None] * 20 + [-50])
        self.assertEqual(momentum20(closes), momentum(closes, MOMENTUM20_POLICY.period))

    def test_10_11_close_readiness_boundary(self):
        self.assertEqual(MOMENTUM10_POLICY.minimum_closes, 11)
        self.assertFalse(is_momentum10_ready(10))
        with self.assertRaises(InsufficientHistoryError) as caught:
            momentum10([100] * 10)
        self.assertEqual((caught.exception.required, caught.exception.available), (11, 10))
        self.assertTrue(is_momentum10_ready(11))
        self.assertEqual(momentum10([100] * 11), [None] * 10 + [0])

    def test_20_21_close_readiness_boundary(self):
        self.assertEqual(MOMENTUM20_POLICY.minimum_closes, 21)
        self.assertFalse(is_momentum20_ready(20))
        with self.assertRaises(InsufficientHistoryError) as caught:
            momentum20([100] * 20)
        self.assertEqual((caught.exception.required, caught.exception.available), (21, 20))
        self.assertTrue(is_momentum20_ready(21))
        self.assertEqual(momentum20([100] * 21), [None] * 20 + [0])

    def test_insufficient_history(self):
        for closes in ([], [10], [10, 11], [10, 11, 12]):
            with self.subTest(closes=closes), self.assertRaises(InsufficientHistoryError) as caught:
                momentum(closes, 3)
            self.assertEqual((caught.exception.required, caught.exception.available), (4, len(closes)))
            self.assertIn("requires 4 closes", str(caught.exception))

    def test_alignment_and_input_immutability(self):
        closes = [100, 125, 75, 100] * 8
        original = closes.copy()
        for calculate, period in ((lambda values: momentum(values, 3), 3), (momentum10, 10), (momentum20, 20)):
            with self.subTest(period=period):
                result = calculate(closes)
                self.assertEqual(len(result), len(closes))
                self.assertEqual(result[:period], [None] * period)
                self.assertTrue(all(value is not None for value in result[period:]))
                self.assertEqual(result, calculate(tuple(closes)))
                result[-1] = -999
                self.assertEqual(closes, original)
        with self.assertRaises(InsufficientHistoryError):
            momentum(closes, len(closes))
        self.assertEqual(closes, original)

    def test_invalid_closes_even_after_readiness(self):
        for value, error in ((0, ValueError), (-1, ValueError), (float("nan"), ValueError),
                             (float("inf"), ValueError), (True, TypeError), ("10", TypeError),
                             (None, TypeError)):
            with self.subTest(value=value), self.assertRaises(error):
                momentum20([10] * 21 + [value])
        with self.assertRaises(TypeError):
            momentum("123", 1)

    def test_invalid_periods_and_readiness_counts(self):
        for value, error in ((-1, ValueError), (True, TypeError), (2.0, TypeError),
                             ("2", TypeError), (None, TypeError)):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    momentum([10, 11, 12], value)
                for ready in (is_momentum10_ready, is_momentum20_ready):
                    with self.assertRaises(error):
                        ready(value)
        with self.assertRaises(ValueError):
            momentum([10, 11], 0)
        self.assertFalse(is_momentum10_ready(0))

    def test_policy_is_immutable(self):
        self.assertEqual(MOMENTUM10_POLICY.period, 10)
        self.assertEqual(MOMENTUM20_POLICY.period, 20)
        for policy in (MOMENTUM10_POLICY, MOMENTUM20_POLICY):
            with self.assertRaises(FrozenInstanceError):
                policy.period = 30

    def test_unrepresentable_percentage_raises(self):
        for closes in ([1e-300, 1e300], [1, 1e307]):
            with self.subTest(closes=closes), self.assertRaises(ValueError):
                momentum(closes, 1)


if __name__ == "__main__":
    unittest.main()
