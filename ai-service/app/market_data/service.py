import logging
from datetime import date
from sqlalchemy.orm import Session
from app.database.models import IngestionRunEntity
from .models import DateRange, normalize_symbol
from .provider import MarketDataProvider
from .repository import MarketDataRepository
from .validator import MarketDataValidator, MissingTradingDaysError

logger = logging.getLogger(__name__)


class MarketDataService:
    def __init__(self, provider: MarketDataProvider, repository: MarketDataRepository):
        self.provider = provider
        self.repository = repository

    async def import_historical_data(self, session: Session, symbol: str,
                                     start_date: date, end_date: date) -> tuple[int, int]:
        symbol = normalize_symbol(symbol)
        DateRange(start_date=start_date, end_date=end_date)
        candles = []
        try:
            candles = await self.provider.get_historical_candles(symbol, start_date, end_date)
            candles = MarketDataValidator.validate_batch(candles, symbol, start_date, end_date)
            MarketDataValidator.validate_trading_days(candles, start_date, end_date)
            saved = self.repository.save_candles(session, candles)
            session.add(IngestionRunEntity(
                symbol=symbol, start_date=start_date, end_date=end_date,
                status="success" if candles else "empty", fetched=len(candles), saved=saved,
            ))
            session.commit()
        except Exception as exc:
            session.rollback()
            # Gap summaries contain only locally computed dates. Other errors may contain secrets.
            error = str(exc) if isinstance(exc, MissingTradingDaysError) else type(exc).__name__
            try:
                session.add(IngestionRunEntity(
                    symbol=symbol, start_date=start_date, end_date=end_date,
                    status="failed", fetched=len(candles) if isinstance(exc, MissingTradingDaysError) else 0,
                    saved=0, error=error,
                ))
                session.commit()
            except Exception:
                session.rollback()
                logger.error("Unable to persist ingestion failure for %s", symbol)
            raise
        if not candles:
            logger.warning("No bars returned for %s (%s through %s); no prices synthesized", symbol, start_date, end_date)
        return len(candles), saved
