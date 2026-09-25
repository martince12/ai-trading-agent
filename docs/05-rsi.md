# Phase 2: Wilder RSI

The public functions in `app.market_analysis.rsi` are `rsi(closes, period)` and
`rsi14(closes)`. The latter reads the central `RsiPolicy` for RSI14. No new dependency
is required. No other indicators or trading decisions are implemented here.

Inputs follow the moving-average contract: finite positive real close prices, oldest
to newest, already validated for chronological order and trading-session completeness.
Input is neither changed nor sorted. Close-only inputs cannot verify timestamps or gaps.

For period `p`, each change is `close[t] - close[t-1]`. Its gain is `max(change, 0)`
and its absolute loss is `max(-change, 0)`. The first RSI needs `p + 1` closes:

```text
initial_avg_gain = sum(gains from the first p changes) / p
initial_avg_loss = sum(absolute losses from the first p changes) / p

avg_gain = (previous_avg_gain * (p - 1) + current_gain) / p
avg_loss = (previous_avg_loss * (p - 1) + current_loss) / p

RS = avg_gain / avg_loss
RSI = 100 - 100 / (1 + RS)
```

Zero changes count among the initial `p` observations. Initialization reuses the
moving-average mean helper. Smoothing evaluates the algebraically equivalent weighted
terms separately (`previous * ((p-1)/p) + current * (1/p)`) to avoid overflowing an
intermediate product; `1/p` comes from the policy's Wilder alpha.

Edge cases are explicit: positive gain with zero loss returns **100**; zero gain with
positive loss returns **0**; both zero returns **50**, the neutral flat-market value
stored in `RsiPolicy.flat_market_value`. This rule applies whenever both smoothed
averages are zero. An unchanged price after a non-flat history retains the prior ratio
while both averages decay; it does not automatically reset RSI to 50.

The returned list aligns with the input and starts with `p` entries of `None`. RSI14's
first value is at index 14 (the fifteenth close). Insufficient input raises the same
`InsufficientHistoryError` used by moving averages, with `required=p+1` and
`available=len(closes)`. Period and close validation reuse moving-average conventions.

```python
from app.market_analysis.rsi import rsi, rsi14
from app.market_analysis.moving_averages import InsufficientHistoryError

rsi([10, 12, 11, 13], 3)  # [None, None, None, 80.0]
rsi14([10] * 15)          # fourteen None entries, then 50.0
```

RSI availability does not bypass the separate 100-candle feature-vector policy.
Its recursive result depends on the supplied history's starting point.

Run the complete suite from `ai-service`, including PostgreSQL integration:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests
```
