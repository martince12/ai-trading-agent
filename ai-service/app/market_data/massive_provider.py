import os
from datetime import date, datetime, timezone

import httpx
from dotenv import load_dotenv

from .models import Candle
from .provider import MarketDataProvider
from .validator import MarketDataValidator


load_dotenv()


class MassiveMarketDataProvider(MarketDataProvider):
    BASE_URL = "https://api.massive.com"

    def __init__(self):
        self.api_key = os.getenv("MASSIVE_API_KEY")

        if not self.api_key:
            raise ValueError("MASSIVE_API_KEY is not set in .env")

    async def get_historical_candles(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[Candle]:

        url = (
            f"{self.BASE_URL}/v2/aggs/ticker/"
            f"{symbol}/range/1/day/{start_date}/{end_date}"
        )

        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 5000,
            "apiKey": self.api_key,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                timeout=30.0,
            )

            response.raise_for_status()
            data = response.json()

        candles = []

        for item in data.get("results", []):
            candle = Candle(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(
                    item["t"] / 1000,
                    tz=timezone.utc,
                ),
                open=item["o"],
                high=item["h"],
                low=item["l"],
                close=item["c"],
                volume=item["v"],
            )

            MarketDataValidator.validate_candle(candle)
            candles.append(candle)

        return candles