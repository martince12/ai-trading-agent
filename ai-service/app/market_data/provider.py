from abc import ABC, abstractmethod
from datetime import date

from .models import Candle


class MarketDataProvider(ABC):

    @abstractmethod
    async def get_historical_candles(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[Candle]:
        pass