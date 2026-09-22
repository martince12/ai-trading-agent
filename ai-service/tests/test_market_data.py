import asyncio
import os
import unittest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

# Never connect tests to the developer's configured database or API.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.database.models import IngestionRunEntity, MarketCandleEntity
from app.main import app, get_session
from app.market_data.massive_provider import MassiveMarketDataProvider, ProviderError
from app.market_data.models import Candle, DateRange
from app.market_data.repository import MarketDataRepository
from app.market_data.service import MarketDataService
from app.market_data.validator import MarketDataValidator, MissingTradingDaysError
from app.market_data.worker import collect_once

# Exact public Massive documentation sample; verifies units and field mapping.
BAR = {"c": 75.0875, "h": 75.15, "l": 73.7975, "o": 74.06, "t": 1577941200000, "v": 135647456}
START, END = date(2020, 1, 2), date(2020, 1, 3)


def candle(**changes):
    values = dict(symbol="AAPL", timestamp=datetime(2020, 1, 2, 5, tzinfo=timezone.utc),
                  open=74.06, high=75.15, low=73.7975, close=75.0875, volume=135647456)
    values.update(changes)
    return Candle(**values)


def payload(bars=None, **changes):
    result = dict(status="OK", ticker="AAPL", adjusted=True, results=[BAR] if bars is None else bars)
    result.update(changes)
    return result


class ValidationTests(unittest.TestCase):
    def test_invalid_prices_volume_and_time(self):
        for change in ({"open": 0}, {"close": float("nan")}, {"high": float("inf")},
                       {"volume": -1}, {"volume": float("inf")}, {"low": 76},
                       {"timestamp": datetime(2020, 1, 2)}, {"symbol": "../evil"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                candle(**change)
        self.assertEqual(candle(symbol=" aapl ", volume=0).symbol, "AAPL")

    def test_dates_and_duplicates(self):
        with self.assertRaises(ValueError):
            DateRange(start_date=END, end_date=START)
        with self.assertRaises(ValueError):
            DateRange(start_date=START, end_date=date(9999, 1, 1))
        self.assertEqual(len(MarketDataValidator.validate_batch([candle(), candle()], "AAPL", START, END)), 1)
        for bars in ([candle(), candle(close=75)], [candle(symbol="MSFT")],
                     [candle(timestamp=datetime(2020, 1, 2, 6, tzinfo=timezone.utc))]):
            with self.assertRaises(ValueError):
                MarketDataValidator.validate_batch(bars, "AAPL", START, END)


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    def provider(self, handler, **kwargs):
        return MassiveMarketDataProvider("test-secret", transport=httpx.MockTransport(handler),
                                        request_interval=0, sleep=AsyncMock(), **kwargs)

    async def test_exact_values_pagination_and_auth(self):
        calls = []
        def handler(request):
            calls.append(request)
            self.assertEqual(request.headers["Authorization"], "Bearer test-secret")
            self.assertNotIn("apiKey", request.url.params)
            if len(calls) == 1:
                self.assertEqual(request.url.params["adjusted"], "true")
                return httpx.Response(200, json=payload(next_url="https://api.massive.com/v2/aggs/ticker/AAPL?cursor=next"))
            return httpx.Response(200, json=payload([{**BAR, "t": 1578027600000}]))
        result = await self.provider(handler).get_historical_candles("aapl", START, END)
        self.assertEqual(result[0], candle())
        self.assertEqual(result[1].timestamp, datetime(2020, 1, 3, 5, tzinfo=timezone.utc))
        self.assertEqual(len(calls), 2)

    async def test_transient_retry_and_retry_after(self):
        responses = [httpx.Response(429, headers={"Retry-After": "3"}),
                     httpx.Response(503), httpx.Response(200, json=payload())]
        provider = self.provider(lambda request: responses.pop(0))
        self.assertEqual(len(await provider.get_historical_candles("AAPL", START, END)), 1)
        provider.sleep.assert_any_await(3)

    async def test_network_retry_exhaustion_and_no_secret(self):
        def handler(request):
            raise httpx.ConnectError("secret in upstream error", request=request)
        provider = self.provider(handler, retries=1)
        with self.assertRaises(ProviderError) as caught:
            await provider.get_historical_candles("AAPL", START, END)
        self.assertNotIn("secret", str(caught.exception))
        self.assertEqual(provider.sleep.await_count, 1)

    async def test_reject_corruption_envelopes_and_pagination(self):
        bad_payloads = [payload([{**BAR, "v": -1}]), payload([{**BAR, "o": None}]),
                        payload([{**BAR, "v": True}]), payload([{**BAR, "t": "1577941200000"}]),
                        payload(resultsCount=3), payload(adjusted=False), payload(ticker="MSFT"),
                        payload(status="ERROR"), payload(next_url="https://evil.example/steal"),
                        payload([{**BAR, "t": 1577944800000}]),
                        payload([BAR, {**BAR, "c": 74}]), []]
        for data in bad_payloads:
            with self.subTest(data=data), self.assertRaises(ProviderError):
                await self.provider(lambda request: httpx.Response(200, json=data)).get_historical_candles("AAPL", START, END)

    async def test_empty_response_and_permanent_failure(self):
        result = await self.provider(lambda r: httpx.Response(200, json=payload([]))).get_historical_candles("AAPL", START, END)
        self.assertEqual(result, [])
        provider = self.provider(lambda r: httpx.Response(403))
        with self.assertRaises(ProviderError):
            await provider.get_historical_candles("AAPL", START, END)
        provider.sleep.assert_not_awaited()

    async def test_second_page_failure_never_returns_partial_data(self):
        responses = [httpx.Response(200, json=payload(next_url="https://api.massive.com/v2/aggs/ticker/AAPL?cursor=next")), httpx.Response(403)]
        with self.assertRaises(ProviderError):
            await self.provider(lambda r: responses.pop(0)).get_historical_candles("AAPL", START, END)


class StorageAndAPITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:",
                                    connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine)
        self.repository = MarketDataRepository()
        self.provider = AsyncMock()
        self.provider.get_historical_candles.return_value = [candle()]
        self.service = MarketDataService(self.provider, self.repository)
        def session_override():
            with self.sessions() as session:
                yield session
        app.dependency_overrides[get_session] = session_override
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def ingest(self, start_date=START, end_date=START):
        with self.sessions() as session:
            return asyncio.run(self.service.import_historical_data(session, "aapl", start_date, end_date))

    def test_roundtrip_idempotence_and_corrections(self):
        self.assertEqual(self.ingest(), (1, 1))
        self.assertEqual(self.ingest(), (1, 0))
        self.provider.get_historical_candles.return_value = [candle(close=75)]
        self.assertEqual(self.ingest(), (1, 1))
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketCandleEntity)), 1)
            self.assertEqual(self.repository.get_latest(session, "AAPL").close, 75)

    def test_corrupt_batch_preserves_previous_data_and_audits_failure(self):
        self.ingest()
        self.provider.get_historical_candles.return_value = [candle(close=75), candle(symbol="MSFT")]
        with self.assertRaises(ValueError):
            self.ingest()
        with self.sessions() as session:
            self.assertEqual(self.repository.get_latest(session, "AAPL"), candle())
            self.assertEqual(session.scalars(select(IngestionRunEntity).order_by(IngestionRunEntity.id)).all()[-1].status, "failed")

    def test_empty_is_audited_without_synthetic_bars(self):
        self.provider.get_historical_candles.return_value = []
        self.assertEqual(self.ingest(date(2020, 1, 4), date(2020, 1, 5)), (0, 0))
        self.assertEqual(self.client.get("/market-data/AAPL/ingestions").json()[0]["status"], "empty")
        self.assertEqual(self.client.get("/market-data/AAPL/latest").status_code, 404)

    def test_database_enforces_constraints(self):
        with self.sessions() as session:
            session.add(MarketCandleEntity(**{**candle().model_dump(), "volume": -1}))
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_api_filtering_pagination_and_exact_ohlcv(self):
        self.provider.get_historical_candles.return_value = [candle(), candle(timestamp=datetime(2020, 1, 3, 5, tzinfo=timezone.utc))]
        self.ingest(end_date=END)
        params = {"start_date": "2020-01-02", "end_date": "2020-01-03", "limit": 1}
        response = self.client.get("/market-data/aapl/candles", params=params)
        self.assertEqual(response.status_code, 200)
        page = response.json()
        self.assertEqual(Candle.model_validate(page["candles"][0]), candle())
        self.assertEqual(page["next_offset"], 1)
        next_page = self.client.get("/market-data/AAPL/candles", params={**params, "offset": 1}).json()
        self.assertIsNone(next_page["next_offset"])
        self.assertTrue(next_page["candles"][0]["timestamp"].startswith("2020-01-03T05:00"))
        one_day = self.client.get("/market-data/AAPL/candles", params={**params, "end_date": "2020-01-02"}).json()
        self.assertIsNone(one_day["next_offset"])
        self.assertEqual(self.client.get("/market-data/MSFT/candles", params=params).json()["count"], 0)
        self.assertEqual(self.client.get("/market-data/AAPL/candles", params={**params, "limit": 0}).status_code, 422)
        self.assertEqual(self.client.get("/market-data/AAPL/candles", params={**params, "end_date": "2019-01-01"}).status_code, 422)
        self.assertEqual(self.client.get("/market-data/invalid!/latest").status_code, 422)

    def test_worker_continues_after_symbol_failure(self):
        async def fetch(symbol, start, end):
            if symbol == "BAD":
                raise ProviderError("Failed")
            return [candle()]
        self.provider.get_historical_candles.side_effect = fetch
        failures = asyncio.run(collect_once(self.service, self.sessions, ["BAD", "AAPL"], START, START))
        self.assertEqual(failures, 1)
        self.assertEqual(self.client.get("/market-data/AAPL/latest").status_code, 200)
        self.assertEqual(self.client.get("/market-data/BAD/ingestions").json()[0]["status"], "failed")

    def test_missing_normal_trading_day_preserves_existing_and_audits(self):
        self.ingest()
        self.provider.get_historical_candles.return_value = [candle(close=75)]
        with self.assertRaises(MissingTradingDaysError) as caught:
            self.ingest(end_date=END)
        self.assertEqual(caught.exception.missing_dates, (END,))
        audit = self.client.get("/market-data/AAPL/ingestions").json()[0]
        self.assertEqual((audit["status"], audit["fetched"], audit["saved"]), ("failed", 1, 0))
        self.assertIn("1 missing XNYS trading days: 2020-01-03", audit["error"])
        with self.sessions() as session:
            self.assertEqual(self.repository.get_latest(session, "AAPL"), candle())
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketCandleEntity)), 1)
        # A later complete fetch repairs the gap through the normal import path.
        self.provider.get_historical_candles.return_value = [candle(), candle(timestamp=datetime(2020, 1, 3, 5, tzinfo=timezone.utc))]
        self.assertEqual(self.ingest(end_date=END), (2, 1))
        self.assertEqual(self.client.get("/market-data/AAPL/ingestions").json()[0]["status"], "success")

    def test_weekend_is_not_a_missing_trading_day(self):
        self.provider.get_historical_candles.return_value = [
            candle(timestamp=datetime(2020, 1, 3, 5, tzinfo=timezone.utc)),
            candle(timestamp=datetime(2020, 1, 6, 5, tzinfo=timezone.utc)),
        ]
        self.assertEqual(self.ingest(date(2020, 1, 3), date(2020, 1, 6)), (2, 2))
        self.assertEqual(self.client.get("/market-data/AAPL/ingestions").json()[0]["status"], "success")

    def test_market_holidays_are_not_missing_trading_days(self):
        self.provider.get_historical_candles.return_value = []
        # Good Friday, observed Independence Day, Juneteenth, exceptional full closure.
        for day in (date(2020, 4, 10), date(2020, 7, 3), date(2024, 6, 19), date(2025, 1, 9)):
            with self.subTest(day=day):
                self.assertEqual(self.ingest(day, day), (0, 0))
                self.assertEqual(self.client.get("/market-data/AAPL/ingestions").json()[0]["status"], "empty")
        self.assertEqual(self.client.get("/market-data/AAPL/latest").status_code, 404)

    def test_complete_valid_range_is_successful(self):
        # July 3 is observed Independence Day; July 4/5 are a weekend. Summer midnight ET is 04:00 UTC.
        self.provider.get_historical_candles.return_value = [
            candle(timestamp=datetime(2020, 7, 2, 4, tzinfo=timezone.utc)),
            candle(timestamp=datetime(2020, 7, 6, 4, tzinfo=timezone.utc)),
        ]
        self.assertEqual(self.ingest(date(2020, 7, 2), date(2020, 7, 6)), (2, 2))
        audit = self.client.get("/market-data/AAPL/ingestions").json()[0]
        self.assertEqual((audit["status"], audit["fetched"], audit["saved"]), ("success", 2, 2))
        self.assertIsNone(audit["error"])

    def test_empty_trading_day_is_failed_without_synthetic_candles(self):
        self.provider.get_historical_candles.return_value = []
        with self.assertRaises(MissingTradingDaysError):
            self.ingest()
        audit = self.client.get("/market-data/AAPL/ingestions").json()[0]
        self.assertEqual((audit["status"], audit["fetched"], audit["saved"]), ("failed", 0, 0))
        self.assertIn("2020-01-02", audit["error"])
        self.assertEqual(self.client.get("/market-data/AAPL/latest").status_code, 404)

    def test_early_close_and_nonmarket_federal_holiday_still_require_bars(self):
        self.provider.get_historical_candles.return_value = []
        for day in (date(2020, 11, 27), date(2020, 10, 12)):
            with self.subTest(day=day), self.assertRaises(MissingTradingDaysError) as caught:
                self.ingest(day, day)
            self.assertEqual(caught.exception.missing_dates, (day,))

    def test_large_gap_summary_fits_existing_audit_column(self):
        self.provider.get_historical_candles.return_value = []
        with self.assertRaises(MissingTradingDaysError) as caught:
            self.ingest(date(2020, 1, 1), date(2020, 12, 31))
        missing = caught.exception.missing_dates
        self.assertGreater(len(missing), 10)
        audit = self.client.get("/market-data/AAPL/ingestions").json()[0]
        self.assertLessEqual(len(audit["error"]), 300)
        self.assertIn(f"{len(missing)} missing", audit["error"])
        self.assertIn(f"+{len(missing) - 10} more", audit["error"])
        self.assertEqual(audit["status"], "failed")


if __name__ == "__main__":
    unittest.main()
