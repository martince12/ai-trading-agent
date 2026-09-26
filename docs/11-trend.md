# Phase 2: deterministic V1 trend

`app.market_analysis.trend` exposes `detect_trend(closes)` (aligned list) and
`latest_trend(closes)` (latest `TrendResult`). `TrendState` contains `BULLISH`,
`BEARISH`, `NEUTRAL`. Each frozen result exposes:

- `state` and total `score`;
- frozen `signals`: `close_vs_ema20`, `ema20_vs_ema50`, `ema20_slope`, `ema50_slope`,
  `macd_histogram`, `momentum20`;
- `ema20_slope_pct` and `ema50_slope_pct`.

The six signals have equal weight. Each contributes +1 for greater/positive, -1 for
less/negative and 0 for exact equality/zero:

| Component | Comparison |
| --- | --- |
| Close vs EMA20 | current close vs current EMA20 |
| EMA20 vs EMA50 | current EMA20 vs current EMA50 |
| EMA20 slope | sign of EMA20 five-session percentage change |
| EMA50 slope | sign of EMA50 five-session percentage change |
| MACD histogram | sign of current MACD(12,26,9) histogram |
| Momentum20 | sign of current 20-session price ROC |

The score is their sum, ranging from -6 to +6. Score >= 3 is `BULLISH`, score <= -3
is `BEARISH`; otherwise it is `NEUTRAL`. No tolerance or rounding is applied before
comparison: even a tiny nonzero floating-point value contributes its sign.

`TREND_POLICY` centralizes the five-session slope lookback and classification thresholds.
Its history minimum is derived from the existing component policies. EMA50 starts at
index 49, so its five-session slope first exists at **index 54**, requiring **55 closes**.
EMA20 slopes, MACD and Momentum20 are already available then. `is_trend_ready(count)`
in the policy module uses this same minimum. The separate 100-candle feature-vector
readiness floor remains unchanged.

The implementation calls the existing `ema20`, `ema50`, `macd_12_26_9`, and `momentum20`
functions. Each EMA slope reuses generic `momentum` on available EMA values:

```text
EMA slope percentage[t] = (EMA[t] / EMA[t-5] - 1) * 100
```

No indicator formulas are reimplemented. All calculations use only observations at or
before the result's index. `detect_trend` returns `None` for the first 54 entries;
later entries contain results, aligned to the supplied closes. Fewer than 55 closes
raises the shared `InsufficientHistoryError` with required/available counts, for either API.

Input must be chronological, session-complete daily closes for one symbol. Shared validation
rejects nonpositive/nonfinite prices and invalid numeric types. Close-only data cannot
independently verify timestamps or gaps. Input is not sorted or mutated. Results depend
on the supplied starting history through the existing recursive indicators.

Examples:

```python
from app.market_analysis.trend import latest_trend

latest_trend([100 + i*i for i in range(80)])    # BULLISH, +6
latest_trend([100] * 80)                      # NEUTRAL, 0
latest_trend([10000 - i*i for i in range(80)])  # BEARISH, -6
```

These are descriptive trend states, not BUY/SELL decisions or confidence percentages.
No support/resistance or AI logic is added.

Run the complete suite from `ai-service`:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests
```
