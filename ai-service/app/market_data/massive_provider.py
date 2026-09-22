import asyncio
import os
import time
from datetime import date, datetime, timezone
from urllib.parse import quote, urlsplit
import httpx
from dotenv import load_dotenv
from .models import Candle, DateRange, normalize_symbol
from .provider import MarketDataProvider
from .validator import MarketDataValidator

load_dotenv()


class ProviderError(RuntimeError):
    """Safe to log: never contains a URL, credential, or response body."""


class MassiveMarketDataProvider(MarketDataProvider):
    BASE_URL = "https://api.massive.com"

    def __init__(self, api_key=None, *, transport=None, request_interval=13.0,
                 retries=3, sleep=asyncio.sleep):
        self.api_key = api_key or os.getenv("MASSIVE_API_KEY")
        if not self.api_key:
            raise ValueError("MASSIVE_API_KEY is not set")
        if request_interval < 0 or retries < 0:
            raise ValueError("Invalid retry or rate limit configuration")
        self.transport = transport
        self.request_interval = request_interval
        self.retries = retries
        self.sleep = sleep
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def _request(self, client, url, params):
        for attempt in range(self.retries + 1):
            async with self._lock:
                delay = self.request_interval - (time.monotonic() - self._last_request)
                if delay > 0:
                    await self.sleep(delay)
                self._last_request = time.monotonic()
                try:
                    response = await client.get(url, params=params)
                except httpx.RequestError:
                    response = None
            if response is not None and 200 <= response.status_code < 300:
                try:
                    return response.json()
                except ValueError:
                    raise ProviderError("Provider returned invalid JSON") from None
            status = response.status_code if response is not None else None
            if status is not None and status != 429 and status < 500:
                raise ProviderError(f"Provider request rejected (HTTP {status})")
            if attempt == self.retries:
                raise ProviderError(f"Provider unavailable after retries (HTTP {status or 'network error'})")
            retry_after = response.headers.get("Retry-After", "0") if response is not None else "0"
            try:
                delay = min(120, max(2 ** attempt, float(retry_after)))
            except ValueError:
                delay = 2 ** attempt
            await self.sleep(delay)

    async def get_historical_candles(self, symbol: str, start_date: date,
                                     end_date: date) -> list[Candle]:
        symbol = normalize_symbol(symbol)
        DateRange(start_date=start_date, end_date=end_date)
        url = f"{self.BASE_URL}/v2/aggs/ticker/{quote(symbol, safe='')}/range/1/day/{start_date}/{end_date}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000}
        candles, visited = [], set()
        async with httpx.AsyncClient(
            transport=self.transport, timeout=30.0, follow_redirects=False,
            headers={"Authorization": f"Bearer {self.api_key}"},
        ) as client:
            while url:
                parsed = urlsplit(url)
                if (parsed.scheme != "https" or parsed.netloc != "api.massive.com"
                        or not parsed.path.startswith("/v2/aggs/ticker/")
                        or url in visited or len(visited) >= 1000):
                    raise ProviderError("Invalid provider pagination URL")
                visited.add(url)
                data = await self._request(client, url, params)
                if not isinstance(data, dict) or data.get("status") not in ("OK", "DELAYED"):
                    raise ProviderError("Provider returned an unsuccessful response")
                if data.get("ticker", symbol) != symbol or data.get("adjusted") is not True:
                    raise ProviderError("Provider returned unexpected symbol or adjustment mode")
                results = data.get("results", [])
                if not isinstance(results, list) or data.get("resultsCount", len(results)) != len(results):
                    raise ProviderError("Provider returned malformed results")
                try:
                    for item in results:
                        if not isinstance(item, dict) or isinstance(item.get("t"), bool) or not isinstance(item.get("t"), int):
                            raise ValueError("Invalid timestamp")
                        if any(isinstance(item.get(key), bool) or not isinstance(item.get(key), (int, float)) for key in ("o", "h", "l", "c", "v")):
                            raise ValueError("Invalid OHLCV number")
                        candles.append(Candle(
                            symbol=symbol,
                            timestamp=datetime.fromtimestamp(item["t"] / 1000, tz=timezone.utc),
                            open=item["o"], high=item["h"], low=item["l"],
                            close=item["c"], volume=item["v"],
                        ))
                except (KeyError, TypeError, ValueError, OverflowError, OSError):
                    raise ProviderError("Provider returned corrupted OHLCV data; batch rejected") from None
                url = data.get("next_url")
                if url is not None and (not isinstance(url, str) or not url):
                    raise ProviderError("Invalid provider pagination URL")
                params = None
        try:
            return MarketDataValidator.validate_batch(candles, symbol, start_date, end_date)
        except ValueError:
            raise ProviderError("Provider returned invalid daily bars; batch rejected") from None
