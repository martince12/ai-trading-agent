import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.market_data.models import Candle
from app.market_analysis import feature_engineering as features
from app.market_analysis.bollinger_bands import bollinger_bands_20_2
from app.market_analysis.macd import MacdResult, macd_12_26_9
from app.market_analysis.momentum import momentum10, momentum20
from app.market_analysis.moving_averages import InsufficientHistoryError
from app.market_analysis.policy import FEATURE_VECTOR_POLICY
from app.market_analysis.rsi import rsi14
from app.market_analysis.support_resistance import detect_support_resistance
from app.market_analysis.trend import latest_trend
from app.market_analysis.volatility import atr14, realized_volatility20
from app.market_analysis.volume import analyze_volume20


def candles(closes=None, volume=100):
    prices = closes if closes is not None else [100.0] * 100
    return [Candle(
        symbol="AAPL", timestamp=datetime(2020, 1, 2, 5, tzinfo=timezone.utc) + timedelta(days=index),
        open=price, high=price + 1, low=price - 1, close=price, volume=volume,
    ) for index, price in enumerate(prices)]


class FeatureEngineeringTests(unittest.TestCase):
    def test_exact_ema_spread_and_positive_price_relationships(self):
        # For closes 100..199, the seeded EMA20 is 189.5 and EMA50 is 174.5.
        result = features.engineer_features(candles(range(100, 200)))
        self.assertAlmostEqual(result.ema_spread_pct, (189.5 / 174.5 - 1) * 100)
        self.assertTrue(result.ema20_above_ema50)
        self.assertTrue(result.price_above_ema20)
        self.assertTrue(result.price_above_ema50)

    def test_negative_and_equal_price_relationships(self):
        for prices in (range(200, 100, -1), [100] * 100):
            with self.subTest(prices=prices):
                result = features.engineer_features(candles(prices))
                self.assertFalse(result.ema20_above_ema50)
                self.assertFalse(result.price_above_ema20)
                self.assertFalse(result.price_above_ema50)
        self.assertEqual(result.ema_spread_pct, 0)

    def test_macd_boolean_signs_and_equality(self):
        for line, signal, expected in ((2, 1, True), (-2, -1, False), (1, 1, False)):
            with self.subTest(line=line), patch.object(features, "macd_12_26_9", return_value=MacdResult(
                [None] * 99 + [line], [None] * 99 + [signal], [None] * 99 + [line - signal],
            )):
                result = features.engineer_features(candles())
                self.assertEqual(result.macd_above_signal, expected)
                self.assertEqual(result.macd_histogram_positive, expected)
                self.assertEqual((result.macd, result.macd_signal, result.macd_histogram),
                                 (line, signal, line - signal))

    def test_exact_bollinger_position_and_bandwidth(self):
        # Alternating 90/110 gives mean 100, population SD 10, bands 80/120.
        result = features.engineer_features(candles([90, 110] * 50))
        self.assertEqual(result.bollinger_position, 0.75)
        self.assertEqual(result.bollinger_bandwidth_pct, 40)

    def test_flat_bands_and_zero_volume(self):
        result = features.engineer_features(candles(volume=0))
        self.assertIsNone(result.bollinger_position)
        self.assertEqual(result.bollinger_bandwidth_pct, 0)
        self.assertIsNone(result.volume_ratio_20)
        self.assertIsNone(result.volume_vs_average_pct)
        self.assertEqual(result.rsi14, 50)

    def test_bollinger_position_is_not_clamped(self):
        for last in (200, 50):
            prices = [100] * 99 + [last]
            result = features.engineer_features(candles(prices))
            if last > 100:
                self.assertGreater(result.bollinger_position, 1)
            else:
                self.assertLess(result.bollinger_position, 0)

    def test_indicator_values_propagate_at_latest_index(self):
        values = candles([100 + index + (index % 7) for index in range(110)])
        values = [value.model_copy(update={"volume": float(10 + index)}) for index, value in enumerate(values)]
        closes = [value.close for value in values]
        result = features.engineer_features(values)
        volume = analyze_volume20([value.volume for value in values])
        atr = atr14(values)
        macd = macd_12_26_9(closes)
        bands = bollinger_bands_20_2(closes)
        expected = {
            "rsi14": rsi14(closes)[-1], "macd": macd.macd[-1],
            "macd_signal": macd.signal[-1], "macd_histogram": macd.histogram[-1],
            "volume_ratio_20": volume.volume_ratio[-1],
            "volume_vs_average_pct": volume.volume_vs_average_pct[-1],
            "atr14": atr.atr[-1], "atr14_pct": atr.atr_pct[-1],
            "realized_volatility_20": realized_volatility20(closes)[-1],
            "momentum_10_pct": momentum10(closes)[-1], "momentum_20_pct": momentum20(closes)[-1],
            "bollinger_position": (closes[-1] - bands.lower[-1]) / (bands.upper[-1] - bands.lower[-1]),
        }
        for name, value in expected.items():
            with self.subTest(feature=name):
                self.assertEqual(getattr(result, name), value)

    def test_support_resistance_prices_and_distances(self):
        values = candles([110] * 100)
        for index in (90, 94):
            values[index] = values[index].model_copy(update={"low": 100.0, "high": 120.0})
        result = features.engineer_features(values)
        source = detect_support_resistance(values)
        self.assertEqual((result.nearest_support, result.nearest_resistance), (100, 120))
        self.assertAlmostEqual(result.distance_to_support_pct, 100 / 11)
        self.assertAlmostEqual(result.distance_to_resistance_pct, 100 / 11)
        self.assertEqual(result.distance_to_support_pct, source.distance_to_support_pct)
        self.assertEqual(result.distance_to_resistance_pct, source.distance_to_resistance_pct)

    def test_absent_support_resistance_stay_none(self):
        result = features.engineer_features(candles())
        for name in ("nearest_support", "nearest_resistance", "distance_to_support_pct", "distance_to_resistance_pct"):
            self.assertIsNone(getattr(result, name))

    def test_trend_and_slopes_propagate(self):
        for prices in ([100 + i*i for i in range(100)], [20000 - i*i for i in range(100)], [100] * 100):
            result = features.engineer_features(candles(prices))
            source = latest_trend(prices)
            self.assertEqual((result.trend_state, result.trend_score), (source.state, source.score))
            self.assertEqual((result.ema20_slope_pct, result.ema50_slope_pct),
                             (source.ema20_slope_pct, source.ema50_slope_pct))

    def test_99_100_boundary_and_empty_input(self):
        self.assertEqual(FEATURE_VECTOR_POLICY.minimum_candles, 100)
        for count in (0, 55, 99):
            with self.subTest(count=count), self.assertRaises(InsufficientHistoryError) as caught:
                features.engineer_features(candles([100] * count))
            self.assertEqual((caught.exception.required, caught.exception.available), (100, count))
        self.assertIsInstance(features.engineer_features(candles()), features.EngineeredFeatures)

    def test_input_and_result_immutability(self):
        values = candles(range(100, 200))
        before = [value.model_dump() for value in values]
        result = features.engineer_features(values)
        self.assertEqual(result, features.engineer_features(tuple(values)))
        self.assertEqual(before, [value.model_dump() for value in values])
        with self.assertRaises(FrozenInstanceError):
            result.trend_score = 0

    def test_invalid_ohlc_order_symbols_and_duplicate_dates(self):
        values = candles()
        for changes in ({"high": 90}, {"close": float("nan")}, {"volume": -1}, {"symbol": "MSFT"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                features.engineer_features([values[0].model_copy(update=changes), *values[1:]])
        with self.assertRaises(ValueError):
            features.engineer_features(values[::-1])
        values[1] = values[1].model_copy(update={"timestamp": values[0].timestamp + timedelta(hours=1)})
        with self.assertRaises(ValueError):
            features.engineer_features(values)

    def test_nonfinite_derived_feature_is_rejected(self):
        with patch.object(features, "ema20", return_value=[1e300]), patch.object(features, "ema50", return_value=[1e-300]):
            with self.assertRaisesRegex(ValueError, "ema_spread_pct"):
                features.engineer_features(candles())


if __name__ == "__main__":
    unittest.main()
