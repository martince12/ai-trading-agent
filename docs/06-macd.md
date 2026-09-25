# Phase 2: MACD

Public API in `app.market_analysis.macd`:

```python
from app.market_analysis.macd import MacdResult, macd, macd_12_26_9

result = macd([2, 4, 6, 10], fast_period=1, slow_period=3, signal_period=2)
result.macd       # [None, None, 2.0, 3.0]
result.signal     # [None, None, None, 2.5]
result.histogram  # [None, None, None, 0.5]

# Standard periods and EMA settings come from the centralized MACD policy:
standard = macd_12_26_9(closes)  # requires at least 34 closes
```

Inputs follow the existing close-price contract: chronological, session-complete,
finite positive real values. The functions do not sort or mutate input. `MacdResult`
has three independently owned lists, each matching the input length. Its attributes
cannot be rebound, but the returned lists can be edited by callers.

## Calculation and alignment

1. Validate periods and input against the complete-output history requirement.
2. Calculate fast and slow EMAs using the existing shared EMA arithmetic. Each is
   seeded by the mean of its first `period` closes, then updated with
   `previous + (2 / (period + 1)) * (current - previous)`.
3. Where both EMAs exist, `MACD = fast EMA - slow EMA`.
4. Pass only available MACD values to the same EMA implementation for the signal.
   Its seed is the mean of the first `signal_period` available MACD values, followed
   by the standard EMA recurrence. No leading `None` values are replaced with zeros.
5. Where the signal exists, `histogram = MACD - signal`.

All three EMAs reuse `_ema_values` in `moving_averages.py`. That internal arithmetic
accepts prepared signed values so a zero or negative MACD is valid; public close-price
validation still rejects nonpositive prices. No EMA arithmetic is duplicated.

With zero-based indices:

| Output | First valid index | Standard 12/26/9 |
| --- | --- | --- |
| MACD line | `max(fast_period, slow_period) - 1` | 25 (26th close) |
| Signal and histogram | `max(fast_period, slow_period) + signal_period - 2` | 33 (34th close) |

All earlier positions in each series are `None`. Generic periods must be positive
integers; equal or reversed fast/slow periods are supported using the same formulas.
Signal period 1 produces a signal equal to MACD and a zero histogram.

Fewer than `max(fast_period, slow_period) + signal_period - 1` closes raises the existing
`InsufficientHistoryError` with `required` and `available` counts. This includes inputs
long enough to compute the MACD line but too short for its signal: the API requires at
least one complete result. The standard function therefore raises below 34 closes.

No bullish/bearish classification, feature vector or trading decision is produced.
The separate 100-candle feature-vector readiness rule remains in effect.

Run the full suite from `ai-service`, including PostgreSQL integration:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests
```
