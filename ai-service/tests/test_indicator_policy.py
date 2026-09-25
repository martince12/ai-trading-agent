import unittest
from dataclasses import FrozenInstanceError

from app.market_analysis.policy import (
    FEATURE_VECTOR_POLICY,
    INDICATOR_POLICIES,
    Indicator,
    get_indicator_policy,
    is_feature_vector_ready,
    is_indicator_ready,
)


class IndicatorPolicyTests(unittest.TestCase):
    def test_individual_readiness_boundaries(self):
        for indicator, minimum in (
            (Indicator.SMA20, 20), (Indicator.SMA50, 50),
            (Indicator.EMA20, 20), (Indicator.EMA50, 50),
            (Indicator.RSI14, 15), (Indicator.MACD_12_26_9, 34),
            (Indicator.BOLLINGER_BANDS_20_2, 20),
        ):
            with self.subTest(indicator=indicator):
                self.assertFalse(is_indicator_ready(indicator, 0))
                self.assertFalse(is_indicator_ready(indicator, minimum - 1))
                self.assertTrue(is_indicator_ready(indicator, minimum))
                self.assertTrue(is_indicator_ready(indicator, minimum + 1))

    def test_string_and_enum_lookup_share_the_same_policy(self):
        for indicator in Indicator:
            with self.subTest(indicator=indicator):
                self.assertIs(get_indicator_policy(indicator.value), get_indicator_policy(indicator))
                self.assertTrue(is_indicator_ready(indicator.value, 100))

    def test_ema_initialization_and_alpha(self):
        for indicator, period in ((Indicator.EMA20, 20), (Indicator.EMA50, 50)):
            with self.subTest(indicator=indicator):
                policy = get_indicator_policy(indicator)
                self.assertEqual(policy.period, period)
                self.assertEqual(policy.initialization, "sma_of_first_period_values")
                self.assertEqual(policy.alpha, 2 / (period + 1))

    def test_rsi_uses_fourteen_changes_and_wilder_smoothing(self):
        policy = get_indicator_policy(Indicator.RSI14)
        self.assertEqual(policy.period, 14)
        self.assertEqual(policy.minimum_closes, 15)
        self.assertEqual(policy.initialization, "mean_gain_and_loss_of_first_period_price_changes")
        self.assertEqual(policy.smoothing, "wilder")
        self.assertEqual(policy.alpha, 1 / 14)

    def test_macd_signal_seed_starts_with_first_available_macd_value(self):
        policy = get_indicator_policy(Indicator.MACD_12_26_9)
        self.assertEqual((policy.fast.period, policy.slow.period, policy.signal.period), (12, 26, 9))
        self.assertEqual(policy.macd_minimum_closes, 26)
        self.assertEqual(policy.minimum_closes, 34)
        self.assertEqual(policy.signal_input, "available_macd_values")
        self.assertEqual(policy.macd_definition, "fast_ema_minus_slow_ema")
        self.assertEqual(policy.histogram_definition, "macd_minus_signal")
        for ema in (policy.fast, policy.slow, policy.signal):
            self.assertEqual(ema.initialization, "sma_of_first_period_values")
            self.assertEqual(ema.alpha, 2 / (ema.period + 1))

    def test_bollinger_uses_shared_sma20_and_population_deviation(self):
        policy = get_indicator_policy(Indicator.BOLLINGER_BANDS_20_2)
        self.assertIs(policy.center, get_indicator_policy(Indicator.SMA20))
        self.assertEqual(policy.standard_deviation_multiplier, 2)
        self.assertEqual(policy.ddof, 0)

    def test_feature_vector_readiness_boundary(self):
        self.assertEqual(FEATURE_VECTOR_POLICY.minimum_candles, 100)
        for count, expected in ((0, False), (99, False), (100, True), (101, True), (254, True)):
            with self.subTest(count=count):
                self.assertEqual(is_feature_vector_ready(count), expected)

    def test_individual_readiness_does_not_bypass_feature_vector_floor(self):
        self.assertEqual(set(FEATURE_VECTOR_POLICY.required_indicators), set(Indicator))
        self.assertTrue(all(is_indicator_ready(indicator, 50) for indicator in Indicator))
        self.assertFalse(is_feature_vector_ready(50))

    def test_invalid_counts_are_rejected(self):
        for count, error in ((-1, ValueError), (20.0, TypeError), ("20", TypeError),
                             (True, TypeError), (False, TypeError), (None, TypeError)):
            with self.subTest(count=count):
                with self.assertRaises(error):
                    is_indicator_ready(Indicator.SMA20, count)
                with self.assertRaises(error):
                    is_feature_vector_ready(count)

    def test_unknown_indicator_is_rejected(self):
        for indicator in ("SMA200", "sma20", ""):
            with self.subTest(indicator=indicator):
                with self.assertRaises(ValueError):
                    get_indicator_policy(indicator)
                with self.assertRaises(ValueError):
                    is_indicator_ready(indicator, 100)

    def test_policy_registry_and_nested_settings_are_immutable(self):
        with self.assertRaises(TypeError):
            INDICATOR_POLICIES[Indicator.SMA20] = get_indicator_policy(Indicator.SMA50)
        with self.assertRaises(FrozenInstanceError):
            get_indicator_policy(Indicator.EMA20).period = 99
        with self.assertRaises(FrozenInstanceError):
            get_indicator_policy(Indicator.MACD_12_26_9).signal.period = 10
        with self.assertRaises(FrozenInstanceError):
            FEATURE_VECTOR_POLICY.minimum_candles = 50


if __name__ == "__main__":
    unittest.main()
