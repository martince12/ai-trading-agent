# Market Data Service

`Massive REST API -> collector -> validation -> PostgreSQL -> FastAPI`

## Provider and data contract

The existing Massive integration is the provider for V1 US stocks. Its official
[custom bars documentation](https://www.massive.com/docs/rest/stocks/aggregates/custom-bars)
defines the daily OHLCV fields, millisecond timestamps, split adjustments and pagination.
Access to historical dates depends on the API account's subscription.

This service stores **one-day, split-adjusted bars from Massive only**. All stored
timestamps are UTC; a bar's market date is determined in `America/New_York`, including
DST. Date ranges are inclusive market dates. Prices are not dividend-adjusted total
returns. Volume is the provider's numeric volume, preserved without integer truncation.
Only dates before today in New York can be imported or queried. Recent completed dates
can still receive provider corrections, which subsequent imports update.

Expected trading dates use the NYSE (`XNYS`) financial calendar from the established
[`holidays` package](https://holidays.readthedocs.io/en/main/auto_gen_docs/ny_stock_exchange/).
It supplies market-specific holidays, observed dates and exceptional closures without
adding pandas/NumPy to the minimal installation; its only runtime dependency is the
already-used `python-dateutil`. Early-close days still require a daily candle.

The existing unique `(symbol, timestamp)` key deliberately supports this one source,
timeframe and adjustment mode. A future provider, intraday timeframe or raw-price series
must extend that key/schema before sharing the table. Prices use the existing SQL
floating-point columns; accounting-grade money calculations need a separate decimal model.

## Setup

From the repository root, start the existing database:

```powershell
docker compose up -d analytics-db
cd ai-service
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-market-data.txt
# For a new setup only; preserve an existing .env and its credentials.
Copy-Item .env.example .env
```

Set `MASSIVE_API_KEY` in `.env`. `DATABASE_URL` in the example connects to the existing
Compose PostgreSQL service on port 55432. Then apply migrations:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
```

The added migration creates ingestion history and OHLCV database constraints. If old
rows violate the constraints, migration fails for explicit investigation; it does not
silently delete historical data.

## Collect historical data and schedule refreshes

```powershell
.venv/Scripts/python.exe import_historical_data.py --symbols AAPL,MSFT --start 2026-08-01 --end 2026-08-31
.venv/Scripts/python.exe -m app.market_data.worker
```

The dedicated worker collects immediately, then waits six hours after each cycle.
Keep this process running under your process supervisor for unattended operation. It
is independent of API workers; restarting/scaling FastAPI does not start duplicate jobs.
`--once` runs a single cycle and exits nonzero if any symbol fails. Ctrl+C stops the worker.

Configuration:

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | required | SQLAlchemy PostgreSQL URL |
| `MASSIVE_API_KEY` | required for collection | Provider credential; read API does not require it |
| `MARKET_DATA_SYMBOLS` | `AAPL,NVDA,MSFT,AMZN,GOOGL` | Comma-separated stock symbols |
| `MARKET_DATA_START_DATE` | one year before worker startup | Beginning of the maintained historical window |
| `MARKET_DATA_INTERVAL_SECONDS` | `21600` | Delay between collection cycles |

The entire configured window is fetched on each cycle so missing/delayed bars and
historical split adjustments can be repaired. Set the start date to the oldest history
you intend to maintain; older stored data outside that window is not refreshed.
For large universes this strategy should evolve to incremental imports plus scheduled
full reconciliation. Requests are paced at least 13 seconds apart within the collector;
other programs sharing the same API key are outside this limiter. PostgreSQL advisory
locking prevents another instance of this collector or the import CLI from running
concurrently. SQLite is supported for isolated tests/local development, without that lock.

## Validation and missing data

- Require finite positive OHLC, finite nonnegative volume, valid high/low relationships,
  matching symbols, requested dates and midnight ET daily timestamps.
- Normalize symbols; sort timestamps; deduplicate identical records; reject conflicting
  duplicates and malformed API responses. A bad row or failed page rejects the entire
  symbol's batch. Existing stored data remains intact.
- After collecting and validating all provider pages, compare received New York market
  dates against every weekday in the inclusive range, excluding NYSE full-day holidays
  and observed/exceptional closures. Missing expected sessions raise
  `MissingTradingDaysError` before any candle is written. The whole incomplete batch is
  rejected; no candles are fabricated, interpolated, deleted or corrected by gap detection.
- Use database upserts to insert new bars and update corrected values in a transaction.
  Unchanged bars are not rewritten. `saved` counts inserted or changed rows.
- Retry network errors, HTTP 429 and 5xx with bounded backoff; honor numeric Retry-After
  up to 120 seconds. Authentication/permission failures fail immediately. Pagination is
  restricted to the provider's HTTPS aggregate endpoint; credentials use an auth header.
- Record each completed attempt in `market_data_ingestion_runs` with `success`, `empty`
  or `failed`, range, counts and a sanitized error type. Worker logs identify failed
  symbols and continue with the others. Abruptly interrupted attempts have no completed
  audit record and are retried on the next run.
- A gap is recorded as `failed`, with `fetched` equal to the validated received count and
  `saved=0`. The existing `error` field records the total missing-session count and first
  ten missing ISO dates, with an explicit remaining count for longer gaps. The exception's
  `missing_dates` attribute contains the full list. This uses the existing schema and
  `/market-data/{symbol}/ingestions` endpoint; no migration is required.
- An empty response is `empty` only if the range has no expected sessions (for example,
  weekends or holidays). Empty responses covering a trading day fail the gap check.
  Later worker cycles retry the configured window; only a complete validated batch is
  stored. The check assesses provider-response completeness, even if the database already
  contains candles for the missing dates.
- The shared NYSE calendar is a baseline for US stocks. It does not know individual
  listing/delisting dates, trading halts or whether a symbol had eligible trades, so such
  absences are flagged for review as well. Calendar updates require updating the dependency;
  there is no live exchange-closure feed or independent second-provider reconciliation.

## Read API

```powershell
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Interactive OpenAPI documentation: `http://127.0.0.1:8000/docs`.

| Endpoint | Result |
| --- | --- |
| `GET /market-data/AAPL/candles?start_date=2026-08-01&end_date=2026-08-31&limit=1000&offset=0` | Ascending OHLCV page with provider, timeframe, adjustment metadata and `next_offset` |
| `GET /market-data/AAPL/latest` | Latest stored candle; 404 if none |
| `GET /market-data/AAPL/ingestions?limit=20` | Most recent completed collection attempts |

Limits: candle page size 1–5000, audit page size 1–100. Invalid symbols, ranges and
pagination parameters return 422. A valid empty historical query returns an empty page.
Reads access the database only; they do not fetch the provider on demand. Offset pagination
is ordered but does not hold a snapshot across concurrent history corrections. This is
an internal service; deployment authentication belongs at the application's service boundary.

## Verification

```powershell
cd ai-service
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

To also verify PostgreSQL upsert counts and roundtrips in a temporary schema that is
rolled back after the test, set `MARKET_DATA_TEST_POSTGRES=1`. It uses the `.env` database
URL, or `MARKET_DATA_TEST_DATABASE_URL` if supplied, and requires schema creation rights.

Offline tests use mocked HTTP and an isolated SQLite database. They verify exact values
from Massive's published example, UTC conversion, pagination, retries, corruption rejection,
atomic storage, correction/idempotence behavior, DB constraints, API responses and worker
failure isolation. Gap tests cover missing weekdays, weekends, market/observed holidays,
exceptional closures, early closes, complete ranges, empty trading days, preservation of
stored data, retry recovery and bounded audit summaries. These tests establish correct
transport/storage behavior, not independent
verification of the provider's real market prices.

For an opt-in, read-only live comparison against Massive (uses your API quota):

```powershell
.venv/Scripts/python.exe verify_market_data.py --symbols AAPL,MSFT --start 2026-08-01 --end 2026-08-31
```

This checks every timestamp and OHLCV value in the requested range, and exits nonzero
on mismatches or provider failures. Provider corrections since the last import can
legitimately produce mismatches; rerun the importer to reconcile them.
