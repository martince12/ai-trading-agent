# Phase 2: unified MarketFeatureVector

```python
from app.market_analysis.feature_vector import build_market_feature_vector

vector = build_market_feature_vector(candles)
```

`build_market_feature_vector(candles: Sequence[Candle]) -> MarketFeatureVector`
returns the latest supplied candle's market state. It takes an immutable tuple
snapshot of the input sequence and calls `engineer_features` exactly once with
all supplied history. It copies the resulting feature values without conversion,
rounding or indicator recalculation, then adds the latest candle's metadata.

`MarketFeatureVector` is a frozen dataclass inheriting `EngineeredFeatures`, so
the engineered schema has one source of truth. All fields are scalar immutable
values. Use the builder for validated construction; like the other analysis
dataclasses, direct dataclass construction does not validate its arguments.

## Complete schema

| Field | Type |
| --- | --- |
| symbol | str |
| timestamp | datetime (UTC, timezone-aware) |
| market_date | date (America/New_York) |
| ema20_above_ema50 | bool |
| ema_spread_pct | float |
| price_above_ema20 | bool |
| price_above_ema50 | bool |
| rsi14 | float |
| macd | float |
| macd_signal | float |
| macd_histogram | float |
| macd_above_signal | bool |
| macd_histogram_positive | bool |
| bollinger_position | float or None |
| bollinger_bandwidth_pct | float |
| volume_ratio_20 | float or None |
| volume_vs_average_pct | float or None |
| atr14 | float |
| atr14_pct | float |
| realized_volatility_20 | float |
| volatility_state | VolatilityState (LOW, MEDIUM, HIGH) |
| momentum_10_pct | float |
| momentum_20_pct | float |
| trend_state | TrendState (BULLISH, NEUTRAL, BEARISH) |
| trend_score | int |
| ema20_slope_pct | float |
| ema50_slope_pct | float |
| nearest_support | float or None |
| nearest_resistance | float or None |
| distance_to_support_pct | float or None |
| distance_to_resistance_pct | float or None |

## Validation and unavailable values

Validation delegates to feature engineering and its existing analysis dependencies:

- The centralized 100-candle floor and required indicator readiness apply.
  Short history raises `InsufficientHistoryError` with required/available counts.
- OHLCV must satisfy the existing Candle contract, all candles must share one
  symbol, timestamps must strictly increase, and New York market dates must be unique.
- Invalid input and nonfinite-output errors propagate unchanged; inputs are
  neither sorted nor modified. Session completeness remains the caller's responsibility.
- Missing support/resistance and associated distances remain `None`.
- Flat-band position and zero-average-volume ratios/percentages remain `None`.
- Numeric types, precision and the `TrendState` / `VolatilityState` enums are preserved. Annualized
  realized volatility remains a decimal, not a formatted percentage string.

The vector adds no trading decisions, confidence scores or AI. Volatility state is
inherited from engineered features alongside the unchanged raw volatility and ATR percentage.
For a historical vector, supply only the history ending at the intended candle.

Run the complete suite from `ai-service`:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests
```
