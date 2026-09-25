# Phase 2: Bollinger Bands

Public API in `app.market_analysis.bollinger_bands`:

```python
from app.market_analysis.bollinger_bands import (
    BollingerBandsResult, bollinger_bands, bollinger_bands_20_2,
)

result = bollinger_bands([1, 3, 7, 5], period=2, multiplier=2)
result.middle  # [None, 2.0, 5.0, 6.0]
result.upper   # [None, 4.0, 9.0, 8.0]
result.lower   # [None, 0.0, 1.0, 4.0]

standard = bollinger_bands_20_2(closes)  # settings from centralized policy
```

Inputs follow the existing finite, positive close-price contract, in chronological
order with one close per validated daily candle. Callers verify session completeness;
the calculation cannot infer dates from closes. Input data is not sorted or mutated.

For the trailing window of `p` closes and multiplier `k`:

```text
middle[t] = SMA(p)[t]
population_mean = sum(window) / p
standard_deviation = sqrt(sum((x - population_mean)^2 for x in window) / p)
upper[t] = middle[t] + k * standard_deviation
lower[t] = middle[t] - k * standard_deviation
```

The middle band reuses the existing `_sma` calculation with the policy's center settings.
Python's `statistics.pstdev` computes population standard deviation (`ddof=0`), not
sample deviation. The policy-backed function reads the period, multiplier and `ddof`
from `BollingerBandsPolicy`; unsupported nonzero `ddof` is rejected. No moving-average
logic is duplicated and no dependency is added.

All three result lists match the input length. The first `p-1` positions are `None`;
the standard `(20,2)` bands first appear at **index 19**, the twentieth close. Fewer
than `p` closes raises the existing `InsufficientHistoryError` with `required` and
`available` counts. Period and close validation use the shared moving-average helpers.

Multipliers must be finite, nonnegative real numbers; booleans and numeric strings
are rejected. Zero produces three coincident bands. Flat prices have zero population
deviation, so upper, middle and lower coincide. Period 1 also gives zero deviation.
The lower band may legitimately be zero or negative and is not clamped. An unrepresentable
floating-point band raises `ValueError` instead of returning infinity.

`BollingerBandsResult` follows the MACD result convention: frozen attributes holding
three independent, caller-owned lists. No interpretation, %B, bandwidth, feature vector
or trading signal is produced. The separate 100-candle feature-vector policy is unchanged.

Run the full suite from `ai-service`, including PostgreSQL integration:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests
```
