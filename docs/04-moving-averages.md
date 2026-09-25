# Phase 2: SMA and EMA

`app.market_analysis.moving_averages` implements SMA and EMA only. It uses the shared
[indicator policy](03-indicator-policy.md), requires no new dependencies and performs
no database writes or trading decisions.

## API and input contract

```python
from app.market_analysis.moving_averages import (
    sma, ema, sma20, sma50, ema20, ema50, InsufficientHistoryError,
)

sma([2, 4, 6, 8, 10], period=3)       # [None, None, 4.0, 6.0, 8.0]
ema([2, 4, 6, 10, 4, 8], period=3)    # [None, None, 4.0, 7.0, 5.5, 6.75]

# Given one symbol's validated candles in chronological order:
closes = [candle.close for candle in candles]
sma_values = sma20(closes)
ema_values = ema50(closes)
```

Inputs are oldest-to-newest real close-price sequences. Values must be finite and
strictly positive; booleans and numeric strings are rejected. Callers must supply
validated, chronological, session-complete data from Phase 1: close-only inputs cannot
prove timestamp ordering or completeness. The functions never sort or mutate input.

Each returned list has the same length and order as the input. Its first `period - 1`
entries are `None`; the first available value is at index `period - 1`. An input with
fewer than `period` closes, including an empty input, raises `InsufficientHistoryError`
(a `ValueError`) with `required` and `available` attributes. Invalid period types raise
`TypeError`; nonpositive periods raise `ValueError`.

The named SMA20/50 and EMA20/50 functions fetch their settings from the immutable policy
registry. Generic functions construct the corresponding policy for the requested period.
EMA uses `EmaPolicy.alpha` and explicitly requires its SMA initialization strategy.
There is no pandas `ewm()` or other external moving-average implementation.

## Formulas

For period `p` and zero-based close sequence `c`, starting at `t = p - 1`:

```text
SMA[t] = (c[t-p+1] + ... + c[t]) / p
EMA[p-1] = (c[0] + ... + c[p-1]) / p
alpha = 2 / (p + 1)
EMA[t] = EMA[t-1] + alpha * (c[t] - EMA[t-1])    for t >= p
```

Means use Python's `math.fsum` on the terms divided by the period to avoid overflowing
the intermediate sum for large finite prices. Computation uses floating-point arithmetic.
SMA computes each trailing window independently; EMA advances recursively from the first
seed. Changing the supplied history's starting point changes the EMA seed and later values.

Individual calculations become available at their policy minimum, independently of the
100-candle `MarketFeatureVector` readiness floor. No feature vector is produced here.

## Tests

From `ai-service`, run all tests including PostgreSQL integration:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests
```
