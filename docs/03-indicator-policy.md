# Phase 2: deterministic indicator policy (V1)

`ai-service/app/market_analysis/policy.py` is the shared source for initialization
parameters and readiness. It contains no indicator calculations, feature values,
trading signals or database access, and requires no new dependencies.

Readiness counts validated daily candles in chronological order, with one close per
candle. Callers must first ensure data quality and expected-session completeness using
Phase 1 validation. Counts are not calendar days, and this policy does not independently
verify gaps, ordering, freshness or whether calculated values exist.

| Indicator enum | First complete output (closes) | Initialization / parameters |
| --- | ---: | --- |
| `SMA20` | 20 | Mean of the trailing 20 closes |
| `SMA50` | 50 | Mean of the trailing 50 closes |
| `EMA20` | 20 | SMA of first 20 closes; then alpha `2 / 21` |
| `EMA50` | 50 | SMA of first 50 closes; then alpha `2 / 51` |
| `RSI14` | 15 | Initial mean gains/losses from first 14 price changes; then Wilder smoothing, alpha `1 / 14` |
| `MACD_12_26_9` | 34 | SMA-seeded EMA12 minus SMA-seeded EMA26; signal is SMA-seeded EMA9 of available MACD values; histogram is MACD minus signal |
| `BOLLINGER_BANDS_20_2` | 20 | SMA20 plus/minus 2 standard deviations of the same 20 closes, population `ddof=0` |

EMA initialization is shared by EMA20/50 and all MACD component EMAs. The first MACD
value exists at close 26; its first nine values end at close 34, when the signal and
histogram also become available. The MACD readiness helper refers to the complete
MACD/signal/histogram output, not just the MACD line.

For subsequent EMA inputs, the prescribed recurrence is
`previous + alpha * (current - previous)`. Wilder's subsequent average gains/losses
use `(previous_average * 13 + current_gain_or_loss) / 14`. These are contracts for
future calculation code, not calculations implemented in this module.

`FEATURE_VECTOR_POLICY` defines the future `MarketFeatureVector` readiness contract:
at least **100 daily candles**, with every listed indicator ready. This is an explicit
V1 history floor, not a guarantee of numerical convergence. The actual feature-vector
value model is not implemented yet. Calculations must use a consistently defined input
history: changing its starting point changes recursive EMA/RSI initialization.

## Python API

```python
from app.market_analysis.policy import (
    Indicator,
    get_indicator_policy,
    is_indicator_ready,
    is_feature_vector_ready,
)

ema = get_indicator_policy(Indicator.EMA50)
ema.period          # 50
ema.alpha           # 2 / 51
ema.initialization  # "sma_of_first_period_values"

is_indicator_ready("SMA20", 19)                  # False
is_indicator_ready(Indicator.SMA20, 20)          # True
is_indicator_ready(Indicator.RSI14, 15)          # True
is_indicator_ready(Indicator.MACD_12_26_9, 33)    # False
is_indicator_ready(Indicator.MACD_12_26_9, 34)    # True
is_feature_vector_ready(99)                     # False
is_feature_vector_ready(100)                    # True
```

Policy objects are frozen dataclasses and the registry is read-only. Lookup accepts
an enum member or its exact string value (`MACD(12,26,9)` and `BollingerBands(20,2)`
for the composite indicators). Unknown names raise `ValueError`. Readiness helpers
reject negative counts with `ValueError` and non-integer counts, including booleans,
with `TypeError`. This is an internal Python API; no HTTP endpoint was added.

Run the focused tests from `ai-service`:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_indicator_policy.py
```
