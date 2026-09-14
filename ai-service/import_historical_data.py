import asyncio
from datetime import date

from app.database.connection import SessionLocal
from app.market_data.massive_provider import MassiveMarketDataProvider
from app.market_data.repository import MarketDataRepository
from app.market_data.service import MarketDataService


SYMBOLS = [
    "AAPL",
    "NVDA",
    "MSFT",
    "AMZN",
    "GOOGL",
]


async def main():
    provider = MassiveMarketDataProvider()
    repository = MarketDataRepository()

    service = MarketDataService(
        provider=provider,
        repository=repository,
    )

    with SessionLocal() as session:
        for symbol in SYMBOLS:
            fetched, saved = await service.import_historical_data(
                session=session,
                symbol=symbol,
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 31),
            )

            print(f"{symbol}: fetched={fetched}, saved={saved}")

            await asyncio.sleep(13)


asyncio.run(main())