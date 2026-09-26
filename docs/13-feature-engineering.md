# Phase 2: feature engineering

`app.market_analysis.feature_engineering.engineer_features(candles)` returns an
immutable `EngineeredFeatures` snapshot for the last supplied candle. This is a
derived-feature result, not the final unified `MarketFeatureVector` or an API/DB
model. No trading decisions, confidence scores or AI are added.

Supply one symbol's validated, chronological, session-complete daily `Candle`
objects. Existing OHLC validation is reused; support/resistance additionally
validates unique New York market dates. Inputs are never modified or sorted.
Session completeness remains the caller's responsibility. All supplied history
is used, including recursive indicator initialization; it is not truncated to 100.

The existing feature-vector policy sets the minimum to **100 candles**, and its
required indicator minima are also respected. Fewer candles raises the shared
`InsufficientHistoryError` with required/available candle counts. The latest candle
is never silently replaced by an earlier one because an optional feature is absent.
For historical analysis pass only the prefix ending at the desired candle.

## Features and sources

| Fields | Source / transformation |
| --- | --- |
| `ema20_above_ema50` | EMA20 > EMA50 |
| `ema_spread_pct` | (EMA20 / EMA50 - 1) * 100 |
| `price_above_ema20`, `price_above_ema50` | Latest close > corresponding EMA |
| `rsi14` | Latest existing RSI14 |
| `macd`, `macd_signal`, `macd_histogram` | Latest existing MACD(12,26,9) components |
| `macd_above_signal` | MACD > signal |
| `macd_histogram_positive` | Histogram > 0 |
| `bollinger_position` | (close - lower) / (upper - lower), using Bollinger(20,2) |
| `bollinger_bandwidth_pct` | (upper - lower) / middle * 100 |
| `volume_ratio_20`, `volume_vs_average_pct` | Existing 20-day volume analysis |
| `atr14`, `atr14_pct` | Existing ATR14 and percentage of close |
| `realized_volatility_20` | Existing annualized 20-return volatility, in decimal units |
| `volatility_state` | VolatilityState enum: LOW, MEDIUM, HIGH relative to recent realized volatility |
| `momentum_10_pct`, `momentum_20_pct` | Existing 10/20-day momentum percentages |
| `trend_state`, `trend_score` | Existing TrendState enum and integer score |
| `ema20_slope_pct`, `ema50_slope_pct` | Existing trend result's five-session EMA slopes |
| `nearest_support`, `nearest_resistance` | Selected cluster prices from existing support/resistance analysis |
| `distance_to_support_pct`, `distance_to_resistance_pct` | Existing support/resistance distances, positive percentages of latest close |

The module calls the existing standard indicator/analysis functions directly;
no indicator formulas or trend/level-selection rules are reimplemented. The
trend function internally computes its own dependencies through existing code.

Realized volatility is computed once and reused for both the raw latest value and
the regime. The regime uses up to 100 available observations including the latest,
with linearly interpolated 33rd/67th percentiles. Strictly below/above gives LOW/HIGH;
all other cases, including equality and constant history, give MEDIUM. At 100 candles,
80 volatility observations are available. ATR percentage and raw volatility remain unchanged.

## Edge cases

- Exact equality produces `False` for all greater-than booleans; no rounding or
  comparison tolerance is added.
- Flat Bollinger Bands have `bollinger_position=None` (undefined division) and
  zero bandwidth. Position is not clamped: outside-band closes may produce values
  below zero or above one.
- A zero trailing average volume preserves `None` for ratio and percentage.
- Missing eligible support/resistance preserves `None` for both the level price
  and its corresponding distance. Levels retain existing swing confirmation delay.
- Nonfinite numeric outputs raise `ValueError` rather than emitting NaN/infinity.
- Other indicator edge cases propagate unchanged, including flat-market RSI=50.

Run the full suite with PostgreSQL integration from `ai-service`:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests
```
