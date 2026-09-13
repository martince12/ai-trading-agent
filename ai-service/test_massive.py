import asyncio
from datetime import date

from app.market_data.massive_provider import MassiveMarketDataProvider


async def main():
    provider = MassiveMarketDataProvider()

    candles = await provider.get_historical_candles(
        symbol="AAPL",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 15),
    )

    for candle in candles:
        print(candle)


asyncio.run(main())