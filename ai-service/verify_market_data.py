"""Read-only comparison of stored OHLCV against freshly fetched provider values."""
import argparse
import asyncio
from datetime import date

from app.database.connection import SessionLocal
from app.market_data.massive_provider import MassiveMarketDataProvider
from app.market_data.models import DateRange, normalize_symbol
from app.market_data.repository import MarketDataRepository


async def verify(symbols, start_date, end_date):
    DateRange(start_date=start_date, end_date=end_date)
    provider = MassiveMarketDataProvider()
    repository = MarketDataRepository()
    failures = 0
    for symbol in symbols:
        try:
            expected = await provider.get_historical_candles(symbol, start_date, end_date)
            with SessionLocal() as session:
                stored, offset = [], 0
                while True:
                    page = repository.get_candles(session, symbol, start_date, end_date, limit=5000, offset=offset)
                    stored.extend(page)
                    if len(page) < 5000:
                        break
                    offset += len(page)
            matches = expected == stored
            failures += int(not matches)
            print(f"{symbol}: provider={len(expected)} stored={len(stored)} exact_match={matches}")
        except Exception as exc:
            failures += 1
            print(f"{symbol}: verification failed ({type(exc).__name__})")
    return int(failures > 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    symbols = list(dict.fromkeys(normalize_symbol(s) for s in args.symbols.split(",") if s.strip()))
    if not symbols:
        parser.error("At least one symbol is required")
    raise SystemExit(asyncio.run(verify(symbols, args.start, args.end)))
