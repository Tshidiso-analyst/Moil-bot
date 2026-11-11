# Multi-market ICT research scanner

This feature adds broker-aware instrument discovery and a deterministic ICT-style
candidate scanner. It is deliberately research-only: it does not place, modify,
or close MT5 orders.

## Instruments

The discovery watchlist includes XAUUSD/GOLD, XAGUSD/SILVER, major and selected
cross-currency pairs, and common index aliases (US30/DJ30, NAS100/USTEC,
SPX500/US500, GER40/DAX40 and UK100/FTSE100). Actual availability is determined
from the connected broker's MT5 symbol catalogue. Broker suffixes and aliases
are mapped to canonical names; unsupported symbols are not fabricated.

## Run locally

With the MT5 desktop terminal running and logged into the desired broker:

```powershell
npm run scan:ict:mt5 -- --timeframe M15 --higher-timeframe H1 --bars 500
```

Use `--include-unwatchlisted` to include broker-listed symbols not in the
built-in watchlist. The command reads completed candles only and prints each
symbol's candidate status and reasons.

## Candidate sequence

A candidate requires all of the following:

1. Directional higher-timeframe bias (last 20 completed HTF candles).
2. A recent buy-side or sell-side liquidity raid and close back inside the range.
3. Directional displacement relative to recent candle bodies.
4. A market-structure shift confirmed by candle-body close.
5. A three-candle fair value gap and a later retracement into that gap.
6. An opposing-range liquidity target with at least the configured reward/risk.

The default time windows are the ICT London (02:00–05:00 New York time) and
New York AM (07:00–10:00 New York time) kill zones. These are configurable at
the evaluator API. Session windows are expressed in New York local time, so
daylight-saving changes are handled by the IANA timezone database.

## Important limitations

This is a candidate/research layer, not a validated profitable strategy.
The higher-timeframe bias is a simple range-midpoint filter, not a complete
daily/H4 dealing-range model. Order blocks, breaker blocks, Judas swings,
economic-calendar blackouts, broker contract sizing, account-currency
conversion, portfolio-level exposure, and account-wide one-trade-per-day
enforcement are not yet wired into this scanner. The existing execution
safety controls remain separate and must not be bypassed.

Do not enable demo or live execution based on scanner output. Validate every
instrument with realistic historical data, spread, slippage, commission,
contract specifications, event filters, and unseen out-of-sample periods.


## Additional portfolio safety utilities

- `risk/mt5_position_sizer.py` calculates a volume estimate from MT5 tick
  size/value and broker min/max/step metadata. It rounds down and rejects a
  minimum volume that would exceed the requested risk budget. The default
  maximum risk cap is 1%.
- `risk/portfolio_guard.py` checks the daily trade count across the whole
  portfolio (not separately per symbol), using a configurable IANA timezone.
  The caller must supply actual account trade records; the helper does not
  persist state or authorize execution.
- These helpers are not yet wired into every execution path. Before demo use,
  integrate them at the central order-authorization boundary and verify MT5
  tick-value currency semantics, commissions, gaps, swaps and broker contract
  specifications. The scanner remains read-only.
