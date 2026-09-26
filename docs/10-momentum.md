# Phase 2: deterministic price momentum (Rate of Change)

Public API in `app.market_analysis.momentum`:

```python
from app.market_analysis.momentum import momentum, momentum10, momentum20
from app.market_analysis.policy import is_momentum10_ready, is_momentum20_ready

momentum([100, 80, 125, 100, 250], period=2)  # [None, None, 25.0, 25.0, 100.0]
momentum10([100] * 10 + [125])               # ten None entries, then 25.0
momentum20([100] * 20 + [50])                # twenty None entries, then -50.0
```

The calculation is endpoint percentage change, not absolute price change, summed daily
returns or log return:

```text
momentum_pct[t] = (close[t] / close[t-period] - 1) * 100
```

Inputs follow the shared finite-positive-close contract and must already be chronological,
daily and session-complete. A close-only series cannot independently verify timestamps
or gaps. No input is changed or sorted. Periods are positive integers; invalid types
(including booleans) raise `TypeError`, invalid values raise `ValueError`. An unrepresentable
floating-point percentage raises `ValueError` instead of emitting infinity.

Each returned list aligns with the original input. The first `period` positions are
`None`, followed by percentages. For lookback `p`, `p+1` closes are required:

| Function | Minimum closes | First valid zero-based index |
| --- | ---: | ---: |
| `momentum(closes, p)` | p + 1 | p |
| `momentum10` | 11 | 10 |
| `momentum20` | 21 | 20 |

Too little history raises the existing `InsufficientHistoryError`, exposing `required`
and `available` counts. No partial or fabricated momentum is returned. Flat endpoints
produce zero; decreasing endpoints produce negative percentages without classification.

The standard wrappers reference frozen `MOMENTUM10_POLICY` and `MOMENTUM20_POLICY` in
the central policy module. Their readiness helpers validate counts and use those same
minimums. The separate 100-candle feature-vector rule is unchanged. No new dependency,
trend classification, trading signal or AI logic is introduced.

Run the complete suite from `ai-service`, including PostgreSQL integration:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests
```
