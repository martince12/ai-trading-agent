"""Dedicated periodic collector: python -m app.market_data.worker [--once]."""
import argparse
import asyncio
import logging
import os
from datetime import date, datetime, timedelta

from sqlalchemy import text

from app.database.connection import SessionLocal, engine
from .massive_provider import MassiveMarketDataProvider
from .models import DateRange, MARKET_TZ, normalize_symbol
from .repository import MarketDataRepository
from .service import MarketDataService

logger = logging.getLogger(__name__)
LOCK_ID = 718205219


async def collect_once(service, session_factory, symbols, start_date, end_date):
    """Isolate symbols so one unavailable ticker does not stop the remaining imports."""
    failures = 0
    for symbol in symbols:
        with session_factory() as session:
            try:
                fetched, saved = await service.import_historical_data(session, symbol, start_date, end_date)
                logger.info("%s: fetched=%s saved=%s", symbol, fetched, saved)
            except Exception as exc:
                failures += 1
                logger.error("%s import failed (%s)", symbol, type(exc).__name__)
    return failures


async def run(args):
    symbols = list(dict.fromkeys(normalize_symbol(s) for s in args.symbols.split(",") if s.strip()))
    if not symbols or args.interval <= 0:
        raise ValueError("Provide symbols and a positive collection interval")
    end_date = args.end or datetime.now(MARKET_TZ).date() - timedelta(days=1)
    DateRange(start_date=args.start, end_date=end_date)
    service = MarketDataService(MassiveMarketDataProvider(), MarketDataRepository())
    # Session-level PostgreSQL lock prevents competing collectors, including manual imports.
    with engine.connect() as connection:
        postgres = connection.dialect.name == "postgresql"
        if postgres:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID})
            connection.commit()
            if not acquired:
                logger.warning("Another market data collector is running")
                return 1
        try:
            while True:
                end_date = args.end or datetime.now(MARKET_TZ).date() - timedelta(days=1)
                failures = await collect_once(service, SessionLocal, symbols, args.start, end_date)
                if args.once:
                    return int(failures > 0)
                await asyncio.sleep(args.interval)
        finally:
            if postgres:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
                connection.commit()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--symbols", default=os.getenv("MARKET_DATA_SYMBOLS", "AAPL,NVDA,MSFT,AMZN,GOOGL"))
    parser.add_argument("--start", type=date.fromisoformat, default=os.getenv("MARKET_DATA_START_DATE", (datetime.now(MARKET_TZ).date() - timedelta(days=365)).isoformat()))
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--interval", type=float, default=os.getenv("MARKET_DATA_INTERVAL_SECONDS", "21600"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
