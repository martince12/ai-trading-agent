# Phase 2: deterministic volatility

`app.market_analysis.volatility` exposes:

```python
true_range(candles)                          # aligned list of True Range values
atr(candles, period)                        # AtrResult: .atr and .atr_pct
atr14(candles)                              # policy-backed Wilder ATR14
log_returns(closes)                         # aligned list, None at index 0
realized_volatility(closes, return_period, annualization_factor)
realized_volatility20(closes)               # 20 returns, sqrt(252), ddof=0
```

The immutable `ATR_POLICY` and `REALIZED_VOLATILITY_POLICY` live in the existing policy
module. `is_atr_ready(count)` and `is_realized_volatility_ready(count)` provide count
readiness. They do not change the separate 100-candle feature-vector policy.

ATR accepts the existing Phase 1 `Candle` objects. It revalidates finite positive OHLC
prices, high/low relationships and the rest of the Candle contract, and requires one
symbol with strictly increasing timestamps. Callers supply daily, session-complete data;
ATR does not fill or independently check missing sessions. Close-only inputs follow
the shared finite-positive-price contract and assume chronological daily observations.
Neither input is sorted or mutated. Result lists align with the original input.

## ATR

```text
TR[0] = high[0] - low[0]
TR[t] = max(high[t] - low[t], abs(high[t] - close[t-1]), abs(low[t] - close[t-1]))
ATR[p-1] = mean(TR[0:p])
ATR[t] = (ATR[t-1] * (p-1) + TR[t]) / p
atr_pct[t] = ATR[t] / close[t] * 100
```

Standard `p=14`. The initial TR uses the first candle's range, so the first ATR requires
**14 candles**, not 15, and occurs at **index 13**. Earlier ATR and percentage positions
are `None`. True Range itself starts at index 0 and requires one candle. A constant price
with high=low=close produces zero ATR and zero percentage. Wilder smoothing is evaluated
with separately scaled weights to avoid intermediate product overflow. An unrepresentable
ATR percentage raises `ValueError` rather than emitting infinity.

## Annualized realized volatility

```text
r[t] = ln(close[t] / close[t-1])
realized_volatility[t] = population_stddev(last 20 returns) * sqrt(252)
```

Population deviation uses divisor **20**, not 19 (`ddof=0`), consistent with the
Bollinger policy. The return window includes the return ending at the current close.
Twenty returns require **21 closes**: the first result is at **index 20**, with the
first 20 entries `None`. Results are annualized decimal values (0.20 means 20% annualized
volatility), while `atr_pct` explicitly uses percentage units. Constant returns, including
flat prices, have zero volatility; floating-point rounding may leave negligible residuals.

Log returns use the equivalent `log1p((current-previous)/previous)` for precision on small
changes, with `log(current)-log(previous)` when the direct ratio would overflow/underflow.
Standard-library `statistics.pstdev` computes population deviation. No dependency is added.

Too little history raises the shared `InsufficientHistoryError` with required/available
counts. Invalid input types raise `TypeError`; invalid values, chronology or OHLC relationships
raise `ValueError`. No volatility classification or trading interpretation is implemented.

Run the full suite from `ai-service`:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests
```
