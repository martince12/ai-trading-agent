# Phase 2: relative volatility regime

`app.market_analysis.volatility_regime.classify_volatility_regime(series)` returns
a `VolatilityState` enum member: `LOW`, `MEDIUM`, or `HIGH`. Supply the chronological,
aligned output of the existing `realized_volatility20(closes)` function. The classifier
does not calculate volatility again or change the supplied sequence.

The frozen `VOLATILITY_REGIME_POLICY` centralizes the 100-observation lookback and
33rd/67th percentile thresholds. Strip only leading warm-up `None` entries, take
the most recent available observations (at most 100, including the latest), then
sort a copy for percentile calculation. For sorted sample x with n observations:

```text
rank = (n - 1) * percentile / 100
i = floor(rank)
fraction = rank - i
threshold = x[i] + (x[min(i + 1, n - 1)] - x[i]) * fraction
```

This defines linear interpolation explicitly without adding a dependency. The
latest chronological observation is LOW if strictly below the lower threshold,
HIGH if strictly above the upper threshold, and MEDIUM otherwise. Equality with
either threshold and constant/zero histories produce MEDIUM. No rounding or
comparison tolerance is applied.

The helper requires at least one available observation; empty/all-None input raises
`InsufficientHistoryError`. Internal/trailing None, negative or nonfinite values
are rejected rather than silently falling back to an older observation. Invalid
numeric types, including booleans, are rejected. One available observation is MEDIUM.

Feature engineering still requires at least 100 daily candles. This gives 80 valid
20-return volatility observations; 120 or more candles supplies the full 100-observation
lookback. Feature engineering calculates the series once and uses it for both
`realized_volatility_20` and `volatility_state`. `atr14_pct` is unchanged.
`MarketFeatureVector` inherits and copies the new enum field without recalculation.

This is a relative classification for one stock and the supplied history, not an
absolute market-wide risk threshold, trading decision, confidence score or AI output.

Run the full suite, including PostgreSQL integration, from `ai-service`:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests
```
