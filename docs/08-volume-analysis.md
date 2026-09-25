# Phase 2: deterministic volume analysis

`app.market_analysis.volume` provides:

```python
from app.market_analysis.volume import (
    average_volume, average_volume20, analyze_volume20, VolumeAnalysisResult,
)
from app.market_analysis.policy import VOLUME_POLICY, is_volume_ready

average_volume([0, 3, 6, 3], period=3)  # [None, None, 3.0, 4.0]
result = analyze_volume20([0] * 19 + [20])
result.average_volume_20[-1]      # 1.0
result.volume_ratio[-1]           # 20.0
result.volume_vs_average_pct[-1]  # 1900.0
```

Inputs are chronological daily volumes for one symbol, already validated for ordering
and session completeness. The Phase 1 volume contract permits zero and fractional values:
all inputs must be finite, nonnegative and below `1e308`. Booleans and numeric strings
are rejected. Inputs are neither sorted nor mutated.

The immutable `VOLUME_POLICY` centralizes the 20-day period, inclusion of the current
candle and undefined ratio for zero averages. `is_volume_ready(count)` checks whether
20 observations are available. Volume readiness is separate from the close-indicator
registry; the existing 100-candle feature-vector floor is unchanged.

For trailing period `p`, the current candle **is included**:

```text
average_volume[t] = sum(volume[t-p+1 : t+1]) / p
volume_ratio[t] = volume[t] / average_volume[t]
volume_vs_average_pct[t] = (volume_ratio[t] - 1) * 100
```

`average_volume` accepts any positive integer period; `average_volume20` returns the
standard average list. `analyze_volume20` returns three independent aligned lists in
`VolumeAnalysisResult`. A shared internal SMA helper supplies the trailing mean without
changing positive-close validation for price indicators.

The first `p-1` positions are `None`; standard volume analysis first becomes available
at **index 19**. If a full window has zero average, its average is **0**, but ratio and
percentage are **None** (undefined division), not fabricated zero or infinity. A zero
current volume with a positive average gives ratio **0** and percentage **-100**.
Insufficient-history None values can be distinguished from zero-average cases through
the average list: it contains None only during the initial window.

Too few observations raises the shared `InsufficientHistoryError` with `required` and
`available` counts and a volume-specific message. Invalid numeric values/period ranges
raise `ValueError`; invalid types raise `TypeError`. Computation uses floating-point
arithmetic. Counts establish history readiness, not whether every ratio is defined.

No volume classification, feature-vector construction or trading interpretation is added.

Run the full suite from `ai-service`:

```powershell
$env:MARKET_DATA_TEST_POSTGRES = "1"
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests
```
