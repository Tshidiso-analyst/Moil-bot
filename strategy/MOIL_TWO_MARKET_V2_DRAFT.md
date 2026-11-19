# MOIL TWO-MARKET V2 — strategy and backtest plan

**Status: DRAFT / UNVALIDATED / NO MT5 ORDERS.** Research universe is exactly XAUUSD (broker alias XAUUSDm) and EURUSD (broker alias must be discovered from MT5). This expands research scope only. Existing gold-only implementation must not be represented as EURUSD-ready.

## Source review gate
Audit actual PDF text with page references and actual video transcripts with timestamps and provenance before claiming source-derived rules. Existing PDF catalog is an inventory, not a content review. Video transcript dataset may not be present in this branch. Treat ICT/SMC hypotheses as unvalidated until tested.

## Shared candidate setup
- D1 confirmed structure bias (two closed candles to confirm pivot), H4 dealing range and premium/discount, H1 OB/FVG context, M15 liquidity sweep -> candle-close MSS/BOS with displacement -> newly formed FVG -> later retest -> next-bar-open simulated entry. Never use forming candles or future-confirmed pivots.
- Trade only aligned higher-timeframe structure; neutral, contradictory, missing or stale data means WAIT.
- Stop beyond sweep invalidation with symbol-specific spread/stop constraints; opposing liquidity target; net estimated reward/risk at least 2.0.
- DST-aware New York sessions; separately evaluate London/NY overlap and NYSE first hour; block high-impact USD events when reliable calendar unavailable. Initially block CPI, NFP, PPI and FOMC days.
- For XAUUSD, evaluate DXY, US nominal/real yields and gold-specific event response only if timestamped data available.
- For EURUSD, evaluate USD/EUR economic calendar (ECB, Fed, CPI, employment, PMI, rate decisions), and USD/EUR macro context only if verified. Do not reuse gold-specific point values, pip sizes, session statistics or macro-direction heuristics.

## Portfolio-wide risk
- **Proposed for backtesting only:** maximum 2% of min(balance,equity) risk per trade across both symbols; never increase volume to meet a preferred lot size. This is not a change to the existing execution-engine 1% hard limit.
- For two entries at the same POI, test a combined 2% risk budget (e.g. 1% each), rather than assuming two independent 2% entries. Liquidity sweeps do not justify widening stops or increasing exposure after a loss.
- Compare 1% and 2% sizing in backtests, including stop-outs caused by liquidity sweeps and portfolio drawdown.
- At most 10 new entries per America/New_York day **combined across EURUSD and XAUUSD**; max 3 simultaneous positions combined; max 3% aggregate risk exposure; 5% daily loss halt.
- 0.02 lots is a preference, not an override of broker min/step, margin or risk cap. Reject orders when minimum volume breaches budget.
- No live/demo MT5 order execution is authorized.

## Backtesting gate (before persistent paper trading)
1. Confirm broker-specific EURUSD and XAUUSDm symbols, historical OHLC completeness, timezone, spread/commission, contract size, volume step, tick value, minimum stops and ZAR conversion.
2. Replay each market separately with strictly chronological data and no lookahead; mark simultaneous portfolio signals for combined risk checks.
3. Compare candidate model to simple breakout baseline. Apply spread, slippage, commissions, stop-first same-bar fill assumption and no fills when prices are unobservable.
4. Use training, validation and untouched chronological holdout plus walk-forward windows. Avoid optimizing on holdout.
5. Report by symbol, by setup and by session: sample size, win rate, net expectancy in R, profit factor, max drawdown, loss streak, rejection reasons, cost sensitivity and out-of-sample degradation.
6. Do not claim profitability or activate orders without reproducible evidence and separate user approval.

## Implementation sequence
A. Source audit and source-backed rule matrix.
B. Shared pure strategy detectors and symbol-specific settings with tests.
C. Gold and EURUSD read-only chart overlays and signal explanations.
D. Backtest engine and two separate reports plus combined portfolio risk replay.
E. Only then consider persistent paper-trading simulation.
