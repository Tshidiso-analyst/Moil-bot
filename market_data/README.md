# Historical Market Data

M04 provides the historical market-data foundation for Moil Bot.

## Responsibilities

- Connect to MetaTrader 5.
- Retrieve OHLCV historical candles.
- Normalize timestamps.
- Validate market-data integrity.
- Save historical datasets locally for analysis.

The MT5 adapter uses the regular MetaTrader 5 terminal configured for the project.

No live trade execution is performed by this module.
