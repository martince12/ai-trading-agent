import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from math import isfinite, log, sqrt

from app.market_data.models import Candle
from app.market_analysis.moving_averages import InsufficientHistoryError
from app.market_analysis.policy import (
    ATR_POLICY, REALIZED_VOLATILITY_POLICY, is_atr_ready, is_realized_volatility_ready,
)
from app.market_analysis.volatility import (
    atr, atr14, true_range, log_returns, realized_volatility, realized_volatility20,
)


def candles(rows):
    return [Candle(symbol="AAPL", timestamp=datetime(2020, 1, 2, 5, tzinfo=timezone.utc) + timedelta(days=i),
                   open=close, high=high, low=low, close=close, volume=0)
            for i, (high, low, close) in enumerate(rows)]


class VolatilityTests(unittest.TestCase):
    def test_manual_true_ranges_with_gaps(self):
        values = candles([(12, 8, 10), (15, 13, 14), (11, 9, 10), (12, 10, 11), (14, 8, 12)])
        # First range=4; gap up/down both give 5 despite intraday range=2.
        self.assertEqual(true_range(values), [4, 5, 5, 2, 6])

    def test_exact_initial_atr_seed_includes_first_candle(self):
        values = candles([(12, 8, 10), (15, 13, 14), (11, 9, 10)])
        result = atr(values, 3)
        self.assertEqual(result.atr[:2], [None, None])
        self.assertAlmostEqual(result.atr[2], 14 / 3)

    def test_subsequent_wilder_atr_values(self):
        values = candles([(12, 8, 10), (15, 13, 14), (11, 9, 10), (12, 10, 11), (14, 8, 12)])
        # Seed=14/3; next=(28/3+2)/3=34/9; next=(68/9+6)/3=122/27.
        result = atr(values, 3)
        for actual, expected in zip(result.atr[2:], [14/3, 34/9, 122/27], strict=True):
            self.assertAlmostEqual(actual, expected)

    def test_atr_percentage_uses_current_close(self):
        values = candles([(12, 8, 10), (14, 10, 12)])
        result = atr(values, 1)
        self.assertEqual(result.atr, [4, 4])
        self.assertEqual(result.atr_pct[0], 40)
        self.assertAlmostEqual(result.atr_pct[1], 100 / 3)

    def test_atr14_boundary_and_policy(self):
        values = candles([(11, 9, 10)] * 16)
        self.assertFalse(is_atr_ready(13))
        with self.assertRaises(InsufficientHistoryError) as caught:
            atr14(values[:13])
        self.assertEqual((caught.exception.required, caught.exception.available), (14, 13))
        self.assertTrue(is_atr_ready(14))
        self.assertEqual(atr14(values[:14]).atr, [None] * 13 + [2])
        self.assertEqual(atr14(values), atr(values, ATR_POLICY.period))

    def test_flat_price_atr(self):
        result = atr14(candles([(10, 10, 10)] * 17))
        self.assertEqual(result.atr, [None] * 13 + [0] * 4)
        self.assertEqual(result.atr_pct, [None] * 13 + [0] * 4)

    def test_manual_log_returns(self):
        actual = log_returns([2, 4, 2, 8, 8])
        self.assertIsNone(actual[0])
        for value, expected in zip(actual[1:], [log(2), -log(2), log(4), 0], strict=True):
            self.assertAlmostEqual(value, expected)

    def test_manual_realized_volatility_population_deviation(self):
        # Returns +/-ln(2); population SD=ln(2), annualization sqrt(4)=2.
        actual = realized_volatility([1, 2, 1, 2, 1], 2, 4)
        self.assertEqual(actual[:2], [None, None])
        for value in actual[2:]:
            self.assertAlmostEqual(value, 2 * log(2))

    def test_standard_realized_volatility_annualization(self):
        closes = [1, 2] * 10 + [1]
        result = realized_volatility20(closes)
        self.assertEqual(result[:20], [None] * 20)
        self.assertAlmostEqual(result[20], log(2) * sqrt(252))
        policy = REALIZED_VOLATILITY_POLICY
        self.assertEqual(result, realized_volatility(closes, policy.return_period, policy.annualization_factor))

    def test_realized_volatility_uses_trailing_return_window(self):
        # Returns ln2, -ln2, 0, 0; trailing two-return SDs ln2, ln2/2, 0.
        result = realized_volatility([1, 2, 1, 1, 1], 2, 1)
        for actual, expected in zip(result[2:], [log(2), log(2)/2, 0], strict=True):
            self.assertAlmostEqual(actual, expected)

    def test_constant_returns_and_flat_closes_have_zero_volatility(self):
        for closes in ([2**i for i in range(24)], [10] * 24):
            with self.subTest(closes=closes):
                self.assertEqual(realized_volatility20(closes), [None] * 20 + [0] * 4)

    def test_realized_volatility_20_21_close_boundary(self):
        self.assertFalse(is_realized_volatility_ready(20))
        with self.assertRaises(InsufficientHistoryError) as caught:
            realized_volatility20([10] * 20)
        self.assertEqual((caught.exception.required, caught.exception.available), (21, 20))
        self.assertTrue(is_realized_volatility_ready(21))
        self.assertEqual(realized_volatility20([10] * 21), [None] * 20 + [0])

    def test_insufficient_history(self):
        for values in ([], candles([(10, 9, 10)])):
            with self.subTest(values=values), self.assertRaises(InsufficientHistoryError) as caught:
                atr(values, 3)
            self.assertEqual((caught.exception.required, caught.exception.available), (3, len(values)))
        for function, required in ((true_range, 1), (log_returns, 2), (realized_volatility20, 21)):
            with self.subTest(function=function.__name__), self.assertRaises(InsufficientHistoryError) as caught:
                function([])
            self.assertEqual(caught.exception.required, required)

    def test_alignment_and_input_immutability(self):
        values = candles([(11, 9, 10)] * 24)
        original = [value.model_dump() for value in values]
        closes = [value.close for value in values]
        result = atr14(values)
        self.assertEqual(result, atr14(tuple(values)))
        for series in (result.atr, result.atr_pct):
            self.assertEqual(len(series), len(values))
            self.assertEqual(series[:13], [None] * 13)
        original_pct = result.atr_pct.copy()
        result.atr[-1] = -1
        self.assertEqual(result.atr_pct, original_pct)
        volatility = realized_volatility20(closes)
        self.assertEqual(len(volatility), len(closes))
        self.assertEqual(volatility, realized_volatility20(tuple(closes)))
        volatility[-1] = -1
        self.assertEqual(closes, [10] * 24)
        self.assertEqual([value.model_dump() for value in values], original)

    def test_invalid_ohlc_is_revalidated(self):
        value = candles([(12, 8, 10)])[0]
        for changes in ({"high": 7}, {"low": 11}, {"open": 13}, {"close": 7},
                        {"high": float("inf")}, {"close": float("nan")}, {"low": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                true_range([value.model_copy(update=changes)])
        with self.assertRaises(TypeError):
            true_range([10])

    def test_candle_order_duplicates_and_mixed_symbols_rejected(self):
        values = candles([(12, 8, 10)] * 2)
        for invalid in ([values[1], values[0]], [values[0], values[0]],
                        [values[0], values[1].model_copy(update={"symbol": "MSFT"})]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                atr(invalid, 1)

    def test_invalid_closes(self):
        for value, error in ((0, ValueError), (-1, ValueError), (float("nan"), ValueError),
                             (float("inf"), ValueError), (True, TypeError), ("2", TypeError)):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    log_returns([1, 2, value])
                with self.assertRaises(error):
                    realized_volatility20([10] * 21 + [value])

    def test_invalid_periods_and_readiness_counts(self):
        for value, error in ((-1, ValueError), (True, TypeError), (2.0, TypeError), ("2", TypeError)):
            with self.subTest(value=value):
                for function in (is_atr_ready, is_realized_volatility_ready):
                    with self.assertRaises(error):
                        function(value)
                with self.assertRaises(error):
                    atr(candles([(10, 10, 10)]), value)
                with self.assertRaises(error):
                    realized_volatility([1, 2, 3], value, 252)
                with self.assertRaises(error):
                    realized_volatility([1, 2, 3], 2, value)
        with self.assertRaises(ValueError):
            realized_volatility([1, 2], 1, 0)

    def test_extreme_price_ratios_remain_finite(self):
        values = [1e-300, 1e300, 1e-300]
        returns = log_returns(values)
        self.assertTrue(all(isfinite(value) for value in returns[1:]))
        self.assertAlmostEqual(returns[1], 600 * log(10))
        self.assertAlmostEqual(returns[2], -600 * log(10))
        self.assertTrue(isfinite(realized_volatility(values, 2, 252)[2]))

    def test_volatility_policies_are_immutable(self):
        self.assertEqual(ATR_POLICY.period, 14)
        self.assertEqual(REALIZED_VOLATILITY_POLICY.return_period, 20)
        self.assertEqual(REALIZED_VOLATILITY_POLICY.ddof, 0)
        with self.assertRaises(FrozenInstanceError):
            ATR_POLICY.period = 10
        with self.assertRaises(FrozenInstanceError):
            REALIZED_VOLATILITY_POLICY.annualization_factor = 365


if __name__ == "__main__":
    unittest.main()
