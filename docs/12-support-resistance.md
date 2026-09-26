# Phase 2: deterministic support and resistance

`app.market_analysis.support_resistance.detect_support_resistance(candles, policy=SUPPORT_RESISTANCE_POLICY)`
returns a frozen `SupportResistanceResult` for the latest supplied daily candle.
It accepts chronological `Candle` objects for one symbol, reuses OHLC validation,
and rejects duplicate New York market dates. Session completeness remains the
caller's responsibility. Input candles are never modified or sorted.

The frozen `SupportResistancePolicy` in the policy module centralizes configurable
defaults: `swing_window=2`, `cluster_tolerance_pct=1.0` (one percent), and
`minimum_touches=2`. `is_support_resistance_ready(count, policy=...)` checks the
minimum input size `2 * swing_window + 1`, or **5 candles** by default. This only
means swing detection can run; it does not guarantee a valid level. Shorter input
raises the existing `InsufficientHistoryError` with required/available candle counts.
The separate feature-vector readiness requirement remains 100 candles.

## Confirmed swings

A high must be strictly greater than every high in the `swing_window` candles on
each side. A low must be strictly lower than every neighboring low. Ties do not
qualify. Each `SwingPoint` records `kind`, `price`, original `index`, New York
`market_date`, and `confirmed_at_index` (touch index plus window).

The first and last `swing_window` candles cannot be swing centers. A default swing
at index 2 becomes confirmed only at index 4. The output is a latest snapshot,
not a historical aligned indicator array. For a historical snapshot, pass only
the prefix ending at that date: future confirmation candles must not be used.

## Deterministic clustering

Pool confirmed highs and lows, then sort a copy by price, index, and kind. Walk
the sorted points, appending to the current cluster only when:

```text
(candidate_price - cluster_min_price) / cluster_min_price <= tolerance_pct / 100
```

Otherwise start a new cluster. Anchoring to the minimum limits each cluster's full
spread and prevents chains of nearby points from bridging distant prices. Zero
tolerance groups exact prices only. No rounding or numerical tolerance is added.

Each frozen `PriceLevel` exposes:

- `price`: arithmetic mean of the cluster's observed swing prices;
- `touches`: distinct candle indices, so a candle qualifying as both a high and low
  cannot satisfy two touches by itself;
- `first_touch_index`, `last_touch_index`, `first_touch_date`, `last_touch_date`.

All clusters, including those below the touch threshold, are exposed in ascending
price order for inspection. Highs and lows can contribute to the same cluster;
support/resistance depends on the representative level relative to the latest close.
The mean is a summary of observed swing prices, not an inferred extra level.

## Selection and distances

Only clusters meeting `minimum_touches` are eligible. Select the greatest eligible
price strictly below the latest close as support and the smallest strictly above
as resistance. A level exactly at the close is neither. No eligible level means
`None`, including its corresponding distance.

```text
distance_to_support_pct = (latest_close - support.price) / latest_close * 100
distance_to_resistance_pct = (resistance.price - latest_close) / latest_close * 100
```

Distances are positive percentages of the latest close. Unrepresentable nonfinite
distances raise `ValueError`. Result fields are `latest_close`, `swings`, `clusters`,
`support`, `resistance`, `distance_to_support_pct`, `distance_to_resistance_pct`.

Example: two confirmed lows at 100 and two confirmed highs at 120, with latest
close 110, produce support 100 (two touches), resistance 120 (two touches), and
both distances approximately 9.0909%. No confirmed swings produces empty tuples
and `None` for both levels and distances.

This component is independent of trend classification and makes no trading decisions.
No dependencies or Phase 1 code changes are required.

Run the complete suite, including the transaction-isolated PostgreSQL integration
test, from `ai-service`:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests
```
