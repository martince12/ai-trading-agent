from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import IngestionRunEntity
from app.market_data.models import Candle, DateRange, normalize_symbol
from app.market_data.repository import MarketDataRepository

app = FastAPI(title="Market Data Service", version="1.0.0")
repository = MarketDataRepository()


def get_session():
    with SessionLocal() as session:
        yield session


Database = Annotated[Session, Depends(get_session)]


def valid_symbol(symbol: str) -> str:
    try:
        return normalize_symbol(symbol)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


class CandlePage(BaseModel):
    symbol: str
    provider: str = "massive"
    timeframe: str = "1day"
    adjusted: bool = True
    start_date: date
    end_date: date
    count: int
    next_offset: int | None
    candles: list[Candle]


@app.get("/market-data/{symbol}/candles", response_model=CandlePage)
def get_candles(symbol: str, start_date: date, end_date: date, session: Database,
                limit: int = Query(1000, ge=1, le=5000),
                offset: int = Query(0, ge=0)):
    symbol = valid_symbol(symbol)
    try:
        DateRange(start_date=start_date, end_date=end_date)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False, include_input=False)) from None
    candles = repository.get_candles(session, symbol, start_date, end_date, limit + 1, offset)
    more = len(candles) > limit
    return CandlePage(symbol=symbol, start_date=start_date, end_date=end_date,
                      count=min(len(candles), limit),
                      next_offset=offset + limit if more else None, candles=candles[:limit])


@app.get("/market-data/{symbol}/latest", response_model=Candle)
def get_latest(symbol: str, session: Database):
    candle = repository.get_latest(session, valid_symbol(symbol))
    if candle is None:
        raise HTTPException(404, "No stored candles for this symbol")
    return candle


@app.get("/market-data/{symbol}/ingestions")
def get_ingestions(symbol: str, session: Database, limit: int = Query(20, ge=1, le=100)):
    runs = session.scalars(select(IngestionRunEntity).where(
        IngestionRunEntity.symbol == valid_symbol(symbol),
    ).order_by(IngestionRunEntity.id.desc()).limit(limit))
    return [{name: getattr(run, name) for name in (
        "id", "symbol", "start_date", "end_date", "completed_at", "status", "fetched", "saved", "error",
    )} for run in runs]
