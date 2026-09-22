from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .connection import Base


class MarketCandleEntity(Base):
    __tablename__ = "market_candles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        CheckConstraint("open > 0 AND open < 1e308 AND high > 0 AND high < 1e308 AND low > 0 AND low < 1e308 AND close > 0 AND close < 1e308", name="ck_market_candle_prices"),
        CheckConstraint("volume >= 0 AND volume < 1e308", name="ck_market_candle_volume"),
        CheckConstraint("low <= open AND low <= close AND high >= open AND high >= close", name="ck_market_candle_ohlc"),
        UniqueConstraint(
            "symbol",
            "timestamp",
            name="uq_market_candle_symbol_timestamp",
        ),
    )


class IngestionRunEntity(Base):
    __tablename__ = "market_data_ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(16))
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    saved: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(300))
