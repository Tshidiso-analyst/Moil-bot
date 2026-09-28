from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def validate(self) -> None:
        if self.high < self.low:
            raise ValueError("Candle high cannot be below low.")

        if self.open < self.low or self.open > self.high:
            raise ValueError("Candle open must be between low and high.")

        if self.close < self.low or self.close > self.high:
            raise ValueError("Candle close must be between low and high.")

        if self.volume < 0:
            raise ValueError("Candle volume cannot be negative.")
