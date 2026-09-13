import asyncio
from datetime import date

from app.database.connection import SessionLocal
from app.market_data.massive_provider import MassiveMarketDataProvider
from app.market_data.repository import MarketDataRepository


async def main():
    provider = MassiveMarketDataProvider()
    repository = MarketDataRepository()

    candles = await provider.get_historical_candles(
        symbol="AAPL",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )

    with SessionLocal() as session:
        saved = repository.save_candles(
            session=session,
            candles=candles,
        )

    print(f"Fetched candles: {len(candles)}")
    print(f"Saved candles: {saved}")


asyncio.run(main())