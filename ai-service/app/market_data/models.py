import re
from datetime import date, datetime, timezone
from typing import Annotated
from zoneinfo import ZoneInfo
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

MARKET_TZ = ZoneInfo("America/New_York")


def normalize_symbol(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Symbol must be a string")
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", value):
        raise ValueError("Invalid US stock symbol (maximum 10 characters)")
    return value


Symbol = Annotated[str, BeforeValidator(normalize_symbol)]
Price = Annotated[float, Field(gt=0, lt=1e308, allow_inf_nan=False)]


class DateRange(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def ordered(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        if self.end_date >= datetime.now(MARKET_TZ).date():
            raise ValueError("end_date must be before today in New York; only completed dates are supported")
        return self


class Candle(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)
    symbol: Symbol
    timestamp: datetime
    open: Price
    high: Price
    low: Price
    close: Price
    volume: float = Field(ge=0, lt=1e308, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_bar(self):
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("Timestamp must be timezone-aware")
        if self.timestamp >= datetime.now(timezone.utc):
            raise ValueError("Timestamp must be in the past")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("OHLC prices must lie within low and high")
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(timezone.utc))
        return self
