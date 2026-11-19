# Two-market January historical replay — operator guide

**Implemented now:** Offline historical CSV replay, event ledger, virtual ZAR 500 balance, cost inputs and a *simple sweep/reclaim baseline*. **Not implemented yet:** validated ICT multi-timeframe signal generator, historical chart playback, actual MT5 history download for EURUSD, news-calendar integration, margin/FX conversions sourced automatically, mark-to-market equity, walk-forward learning and broker demo orders.

## Prepare data
Export **UTC timestamped, fully closed M15 candles** from MT5 for both EURUSD and XAUUSDm, ideally starting before January 2026 for warmup. CSV columns: `timestamp,open,high,low,close`. Each timestamp must be the bar OPEN time. Remove forming candles. Preserve exact timestamps; never fabricate missing history.

Create a local `broker_specs.json` (do **not** commit private account details). Required structure:
```json
{
  "EURUSD": {
    "spread": null,
    "slippage": null,
    "zar_per_price_unit_per_lot": null,
    "min_lot": null,
    "lot_step": null,
    "max_lot": null,
    "commission_zar_per_lot_per_side": null
  },
  "XAUUSD": {
    "spread": null,
    "slippage": null,
    "zar_per_price_unit_per_lot": null,
    "min_lot": null,
    "lot_step": null,
    "max_lot": null,
    "commission_zar_per_lot_per_side": null
  }
}
```
**Replace every null with verified numeric broker information before running.** The conversion `zar_per_price_unit_per_lot` must reflect each symbol's contract size and a point-in-time USD/ZAR conversion if account is ZAR. Using one static conversion over a long replay is a known approximation. Spread and slippage are in the symbol's PRICE units, not pips/points.

## Run in Windows PowerShell
```powershell
python -m pytest backtesting/tests/test_two_market_replay.py backtesting/tests/test_run_two_market_replay.py -q
python -m backtesting.run_two_market_replay --eurusd .\EURUSD_M15.csv --gold .\XAUUSD_M15.csv --specs .\broker_specs.json --start 2026-01-01T00:00:00Z --balance 500 --out .\two_market_replay.json
```
The CLI prints a summary and writes an auditable event JSON. It does **not** guarantee any trades: signals can be absent or rejected due to the R500 account's minimum-lot/risk constraint.

## Safety and known limitations
- The baseline is *not* a full ICT strategy: no D1/H4/H1 alignment, OB/FVG, BOS/CHoCH, Fibonacci, validated calendar or approved session gates.
- The current event replay tracks realized cash balance; **open positions are not marked to market**, and position margin is not modeled. The target flag uses ending realized balance, not a verified net liquidation value. Do not treat this as production-grade backtesting.
- No external MT5 orders are submitted. Test and audit before any attempt to connect order execution.
- Broker min-lot and account-size constraints may reject all trades. Do not override safety limits to manufacture results.
- Tests are committed but have not been run on the user's local machine. Provide test output and actual historical data/specifications for the next integration stage.
