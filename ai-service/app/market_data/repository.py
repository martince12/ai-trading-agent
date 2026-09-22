from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from app.database.models import MarketCandleEntity
from .models import Candle, MARKET_TZ
from .validator import MarketDataValidator


class MarketDataRepository:
    def save_candles(self, session: Session, candles: list[Candle]) -> int:
        """Upsert corrections atomically. Caller owns commit/rollback; unchanged bars count as zero."""
        dialect = session.get_bind().dialect.name
        if dialect not in ("postgresql", "sqlite"):
            raise ValueError("Market data requires PostgreSQL or SQLite")
        insert = pg_insert if dialect == "postgresql" else sqlite_insert
        unique = {}
        for candle in candles:
            MarketDataValidator.validate_candle(candle)
            key = (candle.symbol, candle.timestamp)
            if key in unique and unique[key] != candle:
                raise ValueError("Conflicting duplicate candles")
            unique[key] = candle
        values = [candle.model_dump() for candle in unique.values()]
        saved = 0
        fields = ("open", "high", "low", "close", "volume")
        for offset in range(0, len(values), 100):
            statement = insert(MarketCandleEntity).values(values[offset:offset + 100])
            statement = statement.on_conflict_do_update(
                index_elements=["symbol", "timestamp"],
                set_={name: getattr(statement.excluded, name) for name in fields},
                where=or_(*(getattr(MarketCandleEntity, name) != getattr(statement.excluded, name) for name in fields)),
            )
            # psycopg may report rowcount=-1 for this statement; RETURNING is exact.
            saved += len(session.scalars(statement.returning(MarketCandleEntity.id)).all())
        return saved

    @staticmethod
    def as_candle(entity):
        # SQLite does not preserve timezone information; stored timestamps are always UTC.
        timestamp = entity.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return Candle(symbol=entity.symbol, timestamp=timestamp,
                      **{name: getattr(entity, name) for name in ("open", "high", "low", "close", "volume")})

    def get_candles(self, session, symbol: str, start_date: date, end_date: date,
                    limit=1000, offset=0):
        start = datetime.combine(start_date, time.min, MARKET_TZ).astimezone(timezone.utc)
        end = datetime.combine(end_date + timedelta(days=1), time.min, MARKET_TZ).astimezone(timezone.utc)
        rows = session.scalars(select(MarketCandleEntity).where(
            MarketCandleEntity.symbol == symbol,
            MarketCandleEntity.timestamp >= start,
            MarketCandleEntity.timestamp < end,
        ).order_by(MarketCandleEntity.timestamp).limit(limit).offset(offset))
        return [self.as_candle(row) for row in rows]

    def get_latest(self, session, symbol):
        row = session.scalar(select(MarketCandleEntity).where(
            MarketCandleEntity.symbol == symbol,
        ).order_by(MarketCandleEntity.timestamp.desc()).limit(1))
        return self.as_candle(row) if row else None
