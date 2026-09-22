from datetime import date, timedelta
from holidays import financial_holidays
from .models import Candle, MARKET_TZ


class MissingTradingDaysError(ValueError):
    """Full gap list for callers, with a summary fitting the existing audit column."""

    def __init__(self, missing_dates: list[date]):
        self.missing_dates = tuple(missing_dates)
        preview = ", ".join(day.isoformat() for day in missing_dates[:10])
        remaining = len(missing_dates) - 10
        suffix = f"; +{remaining} more" if remaining > 0 else ""
        super().__init__(f"MissingTradingDaysError: {len(missing_dates)} missing XNYS trading days: {preview}{suffix}")


class MarketDataValidator:
    @staticmethod
    def validate_candle(candle: Candle) -> None:
        Candle.model_validate(candle.model_dump())

    @staticmethod
    def validate_trading_days(candles: list[Candle], start_date: date, end_date: date) -> None:
        """Check the validated provider batch against full-day NYSE closures."""
        closures = financial_holidays(
            "XNYS", years=range(start_date.year, end_date.year + 1),
            observed=True, expand=False,
        )
        if start_date.year < closures.start_year or end_date.year > closures.end_year:
            raise ValueError("Requested range is outside the supported NYSE calendar years")
        received = {candle.timestamp.astimezone(MARKET_TZ).date() for candle in candles}
        missing = []
        for offset in range((end_date - start_date).days + 1):
            day = start_date + timedelta(days=offset)
            # HALF_DAY holidays are intentionally excluded: early closes still need a bar.
            if day.weekday() < 5 and day not in closures and day not in received:
                missing.append(day)
        if missing:
            raise MissingTradingDaysError(missing)

    @classmethod
    def validate_batch(cls, candles: list[Candle], symbol: str,
                       start_date: date, end_date: date) -> list[Candle]:
        unique = {}
        for candle in candles:
            cls.validate_candle(candle)
            local = candle.timestamp.astimezone(MARKET_TZ)
            if candle.symbol != symbol or not start_date <= local.date() <= end_date:
                raise ValueError("Provider returned a symbol or timestamp outside the requested range")
            if (local.hour, local.minute, local.second, local.microsecond) != (0, 0, 0, 0):
                raise ValueError("Daily bar must start at midnight in New York")
            previous = unique.get(candle.timestamp)
            if previous is not None and previous != candle:
                raise ValueError("Provider returned conflicting duplicate candles")
            unique[candle.timestamp] = candle
        return sorted(unique.values(), key=lambda candle: candle.timestamp)
