# MOIL GOLD V1 — research strategy specification

**Status: UNVALIDATED / PAPER-RESEARCH ONLY.** XAUUSD only (broker alias XAUUSDm).
This is a proposed testable strategy, not a claim of profitability or institutional order visibility.
Do not enable MT5 order submission from this document.

## Source provenance and gaps
- Inspected: Trading Strategy Guides, *Lecture 10: Entry Models in SMC — Risk Entries vs Confirmation Entries* (2025), https://tradingstrategyguides.com/lecture-10-entry-models-in-smart-money-concepts-smc-risk-entries-vs-confirmation-entries/ . It distinguishes early risk entries from BOS/MSS-confirmed retest entries. **Use confirmation entries only**.
- Inspected: Inner Circle Trader tutorial, *ICT Top Down Analysis* (2026), https://innercircletrader.net/tutorials/ict-top-down-analysis/ . It uses D1 -> H4 -> H1 -> M15 with premium/discount and HTF alignment.
- User-provided SMC research article (Backtrex): OB/FVG/structure confluence, liquidity sweeps, and explicit risk invalidation; these are hypotheses requiring XAUUSD-specific tests.
- Local Moil-bot registry `knowledge/sources/forex_education_registry.py` validates source metadata but **does not itself prove that PDF content was reviewed**. The two anticipated extracted PDF text paths could not be retrieved from this branch. Do not mark PDF-derived rules as reviewed until exact PDF pages and passages have been indexed and checked.
- Other user links (mother bar, opening-range breakout, candlesticks, price-action mistakes, gold commentary, Scribd, TradingNX, chip stocks): not all were retrievable/verified. **Do not attribute rules to them without reading them.** Chip-stock analysis is outside gold strategy scope.

## Deterministic strategy proposal (thresholds are hypotheses to optimize only on training data)
1. **D1 directional bias:** confirmed swing structure with pivot width 2 closed bars on each side, pivots only available after the 2 right-hand bars close. Require last two confirmed swing highs and lows to be ascending for bullish or descending for bearish; otherwise neutral.
2. **H4 context:** use last confirmed external swing high/low as dealing range. Compute midpoint. Prefer longs below midpoint (discount), shorts above (premium). Mark prior-day high/low, previous-week high/low and H4 liquidity pools. Require H4 structure to agree with D1 or WAIT; do not automatically countertrend trade.
3. **H1 setup:** mark unmitigated FVG (3 closed candles with non-overlapping first/third wicks) and OB candidate (last opposing candle before displacement that subsequently closes beyond a confirmed swing). Record formation time, bounds, mitigation status. OB alone is not an entry.
4. **M15 trigger:** sweep a confirmed liquidity high/low and close back inside; within next 6 closed M15 bars, require candle close through opposing confirmed swing and displacement body >1.5 times mean absolute candle body of preceding 10 closed bars. Require an aligned FVG formed during/after displacement.
5. **Confirmation entry:** after the FVG forms, wait for a *later* candle to retest its bounds and close back in the trade direction. Entry is simulated at the next bar open (not the confirming candle close). No order if entry is not observable without lookahead. Maximum 6 bars between FVG formation and retest; invalidate on opposite structure break or sweep invalidation.
6. **Stop:** beyond sweep extreme plus broker minimum stop buffer and observed spread; target nearest *opposing* H1/H4 liquidity. Require net estimated reward/risk >= 2.0 after broker spread, commission, and slippage. No arbitrary $2 stop.
7. **Session:** calculate New York-local time using IANA America/New_York (DST aware), not fixed UTC offsets. Initial research windows London/NY overlap and NYSE first hour; compare them separately in holdout. No entry outside explicitly tested session.
8. **Calendar:** require a verified, timestamped economic calendar with actual, consensus forecast, previous, release time, impact and currency. Relevant: USD CPI, core CPI, NFP, unemployment, wages, FOMC/rate decisions, PCE, PPI, GDP, retail sales, ISM and major Fed communications. Default BLOCK when feed stale/unavailable. Initial blackout: 60 minutes before to 30 minutes after high-impact USD events; full-day block for CPI, NFP, PPI and FOMC until specifically validated. Forecast vs actual surprise is *context only* and must be interpreted with release timestamp, units, revisions and market response. Never infer gold direction from headline keywords or treat an unreleased actual as known.
9. **Macro context:** record DXY direction, US 10Y nominal yield, real-yield proxy where available, and risk sentiment; if inputs missing, mark macro bias UNKNOWN, not bullish/bearish. Fundamental data must not override a missing price-action confirmation.
10. **Risk and portfolio:** lower(balance,equity)*0.01 per trade maximum; preferred lot cap 0.02, broker min/step enforced, never round up. Maximum 10 entries per New York day, 3 open positions, 3% aggregate exposure, 5% daily loss stop. DEMO order execution remains disabled; REAL disabled. With current R500 ZAR account, observed 0.01-lot $2 stop loses ~R34.44 > R5 budget: reject.
11. **Replay and evaluation:** point-in-time historical calendar snapshots, no future candles, explicit spread/slippage/commission, conservative same-bar stop-before-target, no repainting pivots. Compare with naive breakout baseline; report sample size, net expectancy in R, profit factor, maximum drawdown, loss streaks, win rate, by-session breakdown, and chronological out-of-sample/walk-forward. Require enough samples across market regimes; do not claim an edge before tests.

## State machine
`NO_DATA -> HTF_BIAS -> H4_ZONE -> H1_CONTEXT -> M15_SWEEP -> MSS_DISPLACEMENT -> FVG_FORMED -> RETEST_CONFIRMED -> RISK_CHECK -> PAPER_CANDIDATE`.
Every failed/unknown gate returns `WAIT` or `BLOCKED` with an explicit reason. A PAPER_CANDIDATE is not permission to send an MT5 order.

## Implementation gates
- Source audit: inventory PDFs, extract text with page references, review provenance and license.
- Implement pure deterministic detectors with fixture tests, including contradictory HTFs, DST, stale news, lookahead and dual-hit candles.
- Wire read-only market snapshots D1/H4/H1/M15; display each gate and evidence.
- Backtest net costs and broker volume/risk; report results before persistent paper fills.
- Separate any eventual demo execution approval into an independently verified explicit step.
