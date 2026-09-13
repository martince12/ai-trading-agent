from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import MarketCandleEntity
from .models import Candle


class MarketDataRepository:

    def save_candles(
        self,
        session: Session,
        candles: list[Candle],
    ) -> int:
        saved_count = 0

        for candle in candles:
            existing = session.scalar(
                select(MarketCandleEntity).where(
                    MarketCandleEntity.symbol == candle.symbol,
                    MarketCandleEntity.timestamp == candle.timestamp,
                )
            )

            if existing:
                continue

            entity = MarketCandleEntity(
                symbol=candle.symbol,
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )

            session.add(entity)
            saved_count += 1

        session.commit()

        return saved_count