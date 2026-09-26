import unittest
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.market_data.models import Candle, MARKET_TZ
from app.market_analysis.feature_engineering import EngineeredFeatures, engineer_features
from app.market_analysis.feature_vector import MarketFeatureVector, build_market_feature_vector
from app.market_analysis.moving_averages import InsufficientHistoryError
from app.market_analysis.trend import TrendState


def candles(count=100, flat=False, volume=100):
    return [Candle(
        symbol="AAPL", timestamp=datetime(2020, 1, 2, 5, tzinfo=timezone.utc) + timedelta(days=index),
        open=(price := 110.0 if flat else 100.0 + index + index % 7),
        high=price + 1, low=price - 1, close=price, volume=volume,
    ) for index in range(count)]


class FeatureVectorTests(unittest.TestCase):
    def test_exact_propagation_of_every_feature_and_type(self):
        values = candles(110)
        expected = engineer_features(values)
        vector = build_market_feature_vector(values)
        self.assertEqual({field.name for field in fields(vector)},
                         {field.name for field in fields(EngineeredFeatures)} | {"symbol", "timestamp", "market_date"})
        for field in fields(expected):
            with self.subTest(field=field.name):
                self.assertEqual(getattr(vector, field.name), getattr(expected, field.name))
                self.assertIs(type(getattr(vector, field.name)), type(getattr(expected, field.name)))
        self.assertIsInstance(vector.trend_state, TrendState)

    def test_symbol_and_latest_timestamp(self):
        values = candles(105)
        vector = build_market_feature_vector(values)
        self.assertEqual(vector.symbol, values[-1].symbol)
        self.assertEqual(vector.timestamp, values[-1].timestamp)
        self.assertEqual(vector.market_date, values[-1].timestamp.astimezone(MARKET_TZ).date())
        self.assertEqual(vector.timestamp.tzinfo, timezone.utc)

    def test_market_date_uses_new_york_not_utc(self):
        values = candles()
        # Advance latest timestamp within the same NY session but into next UTC day.
        latest = values[-1].timestamp + timedelta(hours=20)
        values[-1] = values[-1].model_copy(update={"timestamp": latest})
        vector = build_market_feature_vector(values)
        self.assertEqual(vector.timestamp, latest)
        self.assertEqual(vector.market_date, latest.astimezone(MARKET_TZ).date())
        self.assertNotEqual(vector.market_date, latest.date())

    def test_99_100_boundary_and_empty_history(self):
        for count in (0, 99):
            with self.subTest(count=count), self.assertRaises(InsufficientHistoryError) as caught:
                build_market_feature_vector(candles(count))
            self.assertEqual((caught.exception.required, caught.exception.available), (100, count))
        self.assertIsInstance(build_market_feature_vector(candles(100)), MarketFeatureVector)

    def test_mixed_symbols_rejected(self):
        values = candles()
        values[40] = values[40].model_copy(update={"symbol": "MSFT"})
        with self.assertRaises(ValueError):
            build_market_feature_vector(values)

    def test_non_chronological_and_duplicate_input_rejected(self):
        values = candles()
        for invalid in (values[::-1], [values[0], *values[:-1]]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                build_market_feature_vector(invalid)
        values[1] = values[1].model_copy(update={"timestamp": values[0].timestamp + timedelta(hours=1)})
        with self.assertRaises(ValueError):
            build_market_feature_vector(values)

    def test_optional_values_remain_none(self):
        vector = build_market_feature_vector(candles(flat=True, volume=0))
        for name in ("nearest_support", "nearest_resistance", "distance_to_support_pct", "distance_to_resistance_pct",
                     "bollinger_position", "volume_ratio_20", "volume_vs_average_pct"):
            with self.subTest(field=name):
                self.assertIsNone(getattr(vector, name))

    def test_available_support_resistance_propagate(self):
        values = candles(flat=True)
        for index in (90, 94):
            values[index] = values[index].model_copy(update={"low": 100.0, "high": 120.0})
        vector = build_market_feature_vector(values)
        expected = engineer_features(values)
        self.assertEqual((vector.nearest_support, vector.nearest_resistance), (100, 120))
        self.assertEqual(vector.distance_to_support_pct, expected.distance_to_support_pct)
        self.assertEqual(vector.distance_to_resistance_pct, expected.distance_to_resistance_pct)

    def test_input_and_vector_immutability(self):
        values = candles()
        original = [candle.model_dump() for candle in values]
        vector = build_market_feature_vector(values)
        self.assertEqual(vector, build_market_feature_vector(tuple(values)))
        self.assertEqual(original, [candle.model_dump() for candle in values])
        for name, replacement in (("symbol", "MSFT"), ("ema_spread_pct", 0), ("trend_state", TrendState.NEUTRAL)):
            with self.subTest(field=name), self.assertRaises(FrozenInstanceError):
                setattr(vector, name, replacement)

    def test_engineering_is_called_once_with_full_history(self):
        values = candles(110)
        with patch("app.market_analysis.feature_vector.engineer_features", wraps=engineer_features) as source:
            build_market_feature_vector(values)
        source.assert_called_once_with(tuple(values))

    def test_invalid_ohlcv_rejected(self):
        values = candles()
        for changes in ({"high": 1}, {"volume": -1}, {"close": float("nan")}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                build_market_feature_vector([values[0].model_copy(update=changes), *values[1:]])


if __name__ == "__main__":
    unittest.main()
