from datetime import date

from sqlalchemy.orm import Session

from .provider import MarketDataProvider
from .repository import MarketDataRepository


class MarketDataService:

    def __init__(
        self,
        provider: MarketDataProvider,
        repository: MarketDataRepository,
    ):
        self.provider = provider
        self.repository = repository

    async def import_historical_data(
        self,
        session: Session,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> tuple[int, int]:

        candles = await self.provider.get_historical_candles(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        saved_count = self.repository.save_candles(
            session=session,
            candles=candles,
        )

        return len(candles), saved_count