import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from app.market_analysis.feature_engineering import engineer_features
from app.market_analysis.feature_vector import build_market_feature_vector
from app.market_analysis.moving_averages import InsufficientHistoryError
from app.market_analysis.policy import VOLATILITY_REGIME_POLICY
from app.market_analysis.volatility import realized_volatility20
from app.market_analysis.volatility_regime import (
    VolatilityState, _percentile, classify_volatility_regime,
)
from test_feature_vector import candles


class VolatilityRegimeTests(unittest.TestCase):
    def test_clearly_low(self):
        self.assertEqual(classify_volatility_regime([None] * 20 + [0.3] * 79 + [0.1]), VolatilityState.LOW)

    def test_clearly_high(self):
        self.assertEqual(classify_volatility_regime([None] * 20 + [0.3] * 79 + [0.9]), VolatilityState.HIGH)

    def test_medium(self):
        self.assertEqual(classify_volatility_regime([0.1] * 40 + [0.9] * 39 + [0.5]), VolatilityState.MEDIUM)

    def test_equality_at_both_percentile_boundaries(self):
        # Both thresholds sit within repeated values: p33=1 and p67=3.
        for latest in (1, 3):
            with self.subTest(latest=latest):
                self.assertEqual(classify_volatility_regime([1] * 39 + [2] * 20 + [3] * 40 + [latest]),
                                 VolatilityState.MEDIUM)

    def test_constant_and_single_observation_are_medium(self):
        for series in ([0] * 80, [0.25] * 150, [None] * 20 + [0.7]):
            with self.subTest(series=series):
                self.assertEqual(classify_volatility_regime(series), VolatilityState.MEDIUM)

    def test_exact_linear_percentiles(self):
        self.assertAlmostEqual(_percentile([0, 10, 20, 30], 33), 9.9)
        self.assertAlmostEqual(_percentile([0, 10, 20, 30], 67), 20.1)
        self.assertEqual(_percentile([0.25], 33), 0.25)

    def test_most_recent_100_observations_only(self):
        recent = [0.3] * 99 + [0.1]
        self.assertEqual(classify_volatility_regime([0.01] * 1000 + recent), VolatilityState.LOW)
        self.assertEqual(classify_volatility_regime([None] * 20 + recent), VolatilityState.LOW)

    def test_latest_is_included_in_percentile_sample(self):
        # With latest included, p67=2.01 so 2 is medium. Without it p67=1.68 -> high.
        self.assertEqual(classify_volatility_regime([0, 1, 3, 2]), VolatilityState.MEDIUM)

    def test_exact_feature_and_vector_propagation_without_recalculation(self):
        values = candles()
        for latest, expected in ((0.1, VolatilityState.LOW), (0.3, VolatilityState.MEDIUM), (0.9, VolatilityState.HIGH)):
            series = [None] * 20 + [0.3] * 79 + [latest]
            for builder in (engineer_features, build_market_feature_vector):
                with self.subTest(builder=builder.__name__, state=expected), patch(
                    "app.market_analysis.feature_engineering.realized_volatility20", return_value=series,
                ) as calculate:
                    result = builder(values)
                calculate.assert_called_once()
                self.assertIs(result.volatility_state, expected)
                self.assertEqual(result.realized_volatility_20, latest)
                self.assertGreater(result.atr14_pct, 0)

    def test_real_indicator_integration_and_readiness(self):
        values = candles()
        expected = classify_volatility_regime(realized_volatility20([value.close for value in values]))
        self.assertIs(engineer_features(values).volatility_state, expected)
        self.assertIs(build_market_feature_vector(values).volatility_state, expected)
        self.assertIs(build_market_feature_vector(candles(flat=True)).volatility_state, VolatilityState.MEDIUM)
        for builder in (engineer_features, build_market_feature_vector):
            with self.assertRaises(InsufficientHistoryError) as caught:
                builder(values[:99])
            self.assertEqual(caught.exception.required, 100)

    def test_input_immutability(self):
        series = [None] * 20 + [0.5, 0.2, 0.8, 0.4]
        original = series.copy()
        state = classify_volatility_regime(series)
        self.assertEqual(series, original)
        self.assertIs(state, classify_volatility_regime(tuple(series)))
        values = candles()
        before = [value.model_dump() for value in values]
        build_market_feature_vector(values)
        self.assertEqual(before, [value.model_dump() for value in values])

    def test_invalid_series(self):
        for series in ([], [None] * 20):
            with self.assertRaises(InsufficientHistoryError):
                classify_volatility_regime(series)
        for series in ([0.2, None], [0.2, None, 0.3], [-0.1], [float("nan")], [float("inf")]):
            with self.subTest(series=series), self.assertRaises(ValueError):
                classify_volatility_regime(series)
        for series in ([True], ["0.2"]):
            with self.assertRaises(TypeError):
                classify_volatility_regime(series)

    def test_centralized_policy_is_frozen(self):
        self.assertEqual((VOLATILITY_REGIME_POLICY.lookback, VOLATILITY_REGIME_POLICY.lower_percentile,
                          VOLATILITY_REGIME_POLICY.upper_percentile), (100, 33, 67))
        with self.assertRaises(FrozenInstanceError):
            VOLATILITY_REGIME_POLICY.lookback = 20


if __name__ == "__main__":
    unittest.main()
