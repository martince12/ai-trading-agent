from .models import Candle


class MarketDataValidator:

    @staticmethod
    def validate_candle(candle: Candle) -> None:
        if candle.open <= 0:
            raise ValueError("Open price must be greater than 0")

        if candle.high <= 0:
            raise ValueError("High price must be greater than 0")

        if candle.low <= 0:
            raise ValueError("Low price must be greater than 0")

        if candle.close <= 0:
            raise ValueError("Close price must be greater than 0")

        if candle.volume < 0:
            raise ValueError("Volume cannot be negative")

        if candle.high < candle.low:
            raise ValueError("High price cannot be lower than low price")

        if candle.high < candle.open or candle.high < candle.close:
            raise ValueError("High price must be >= open and close")

        if candle.low > candle.open or candle.low > candle.close:
            raise ValueError("Low price must be <= open and close")