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

## January 2026 historical replay specification (planned, not yet implemented)
- Default replay start **2026-01-01 00:00:00 UTC**; end at last available fully closed historical candle, never the future. Download enough pre-January D1/H4/H1/M15 warmup candles for confirmed pivots and unmitigated zones. If broker history does not reach January, stop and report the missing period; do not invent candles.
- **Simulated demo account**, separate from broker account: user-configurable starting equity, currency (e.g. ZAR), leverage, and broker specifications. Use the user's chosen demo amount; never silently substitute an MT5 account balance or assume that an MT5 demo trade was actually placed.
- One chronological event clock for both EURUSD and XAUUSDm. Each closed candle becomes visible only at its actual close time; HTF candles are visible to M15 only after their HTF close. The replay must prevent lookahead in pivots, zone mitigation, news and signal confirmation.
- Recompute D1 bias -> H4 dealing range/targets -> H1 liquidity/OB/FVG -> M15 sweep/MSS/CHoCH/BOS/displacement and later OB/FVG/Fibonacci retest at each eligible decision time. Preserve POI IDs, creation time, upper/lower bounds, source timeframe, mitigated/invalidated status and whether the first CHoCH or later BOS created the POI.
- Primary entry model: sweep -> close-confirmed change of character / market structure shift -> displacement and first valid OB/FVG -> later retest in 50%-61.8% M15 impulse retracement, with deeper 61.8%-78.6% and shallow 30%-38.2% variants tested separately. Continuation model: close-confirmed BOS -> new POI/support-resistance flip -> later retest. No automatic claim that a BOS guarantees a retest or that all liquidity must be swept.
- On each eligible POI, **up to two simulated positions** subject to a combined POI risk budget of 2% (example: 1% each); also run 1% baseline. Maximum three simultaneous positions and 3% combined portfolio risk, 10 new positions per New York day across both symbols, 5% daily loss stop. Broker volume minimums, steps, margin, tick values, FX conversion, spreads, commission and slippage are mandatory inputs; reject any impossible trade.
- Signal confirmed at closed bar -> fill no earlier than next available bar's executable ask (buy) or bid (sell), with costs. Stops and targets evaluated using bid/ask and available bar high/low. If both stop and target are touched inside a bar and tick order is unknown, conservatively fill stop first. Never invent fills from the candle close. Support optional partial take-profits only as a separately labeled test variant.
- Trade event log: `event_id, timestamp_utc, symbol, timeframe, setup_id, poi_id, model, action (SIGNAL/REJECT/OPEN/PARTIAL_CLOSE/STOP/TAKE_PROFIT/EXIT), side, quantity, fill_price, stop, target, spread, commission, slippage, risk_currency, realized_pnl, unrealized_pnl, balance_after, equity_after, reason, source_candle_ids`. Include rejected candidates and WAIT reasons. Ensure account balances reconcile exactly to fills and fees.
- Replay controls: date picker, start/pause/step/speed, chart timeframe, symbol, overlay toggles, and ledger filters. Plot historical candles, confirmed swings, liquidity, OB/FVG boxes, Fibonacci, CHoCH/BOS, open/close arrows, SL/TP and running balance/equity/drawdown. UI must clearly label **SIMULATED HISTORICAL FILLS — NOT MT5 ORDERS**.
- Learning means **bounded offline optimization**, not changing rules using future data: train on older chronological windows, select parameters on validation, freeze them for subsequent unseen walk-forward windows, and record version/hash of every parameter set and dataset. Keep January-onward holdout untouched until chosen; if January is the requested demonstration period, train on pre-January history or split January onward chronologically, disclosing which dates are in-sample.
- Backtest both symbols independently and as a combined portfolio. Report entry/exit timestamps, reason for each close, net P/L in demo currency, risk multiple, costs, win rate, profit factor, expectancy, maximum drawdown, trade count, risk-limit rejections, by-session statistics and differences between 1% and 2%. Never claim strategy has learned or become profitable without observed test results.

## Build and acceptance criteria
1. Verify source PDFs/transcripts and extract auditable rules; do not claim review from catalog metadata alone.
2. Add EURUSD to explicit symbol allowlists, market-history retrieval, risk calculations, strategy and dashboard tests without broadening beyond EURUSD and XAUUSD. Preserve existing production safety limits until independently approved.
3. Implement deterministic multi-timeframe strategy and event-driven two-symbol replay with unit tests for DST, close-time alignment, no lookahead, simultaneous signals, position caps, intrabar ambiguity, spread, commissions, min volume, margin, equity reconciliation and daily loss halt.
4. Add saved replay dataset and auditable trade ledger, then build interactive playback chart and virtual account dashboard.
5. Run reproducible January-2026-onward historical backtest with verified broker data, training/validation/holdout split, 1%-vs-2% comparison and clear limitations.
6. **Only after tests pass**, fast-forward the local Windows checkout using `git pull --ff-only origin codex/xauusd-market-data-safety` and run focused and full regression suites. Do not treat a GitHub commit as proof the local VS Code checkout is updated.
7. No real or demo MT5 broker orders from historical replay; any future demo order-execution feature requires separate design, tests and explicit authorization.

## User-defined R500 to R20,000 research challenge
- Historical replay initial virtual account **ZAR 500** and aspirational target **ZAR 20,000** (40x initial capital; +3,900% cumulative return). This is a measurement target, not a promised result, minimum performance requirement, or justification for higher risk.
- Start historical replay at 2026-01-01, with earlier candles as warmup where available. Record the first timestamp the simulated **net liquidation equity** reaches or exceeds ZAR 20,000, if ever; otherwise report not reached. Do not confuse unrealized peak equity with withdrawable realized balance.
- Report target progress, net return, time to target, peak-to-trough drawdown, number of trades, risk of ruin and sensitivity to broker costs. Compare 1% vs proposed 2% per-trade risk with combined POI budget and all existing portfolio constraints.
- No doubling down, martingale, revenge trading, forced signals, or risk-limit relaxation to reach target. If minimum broker volume would exceed the R10 2%-risk allowance on ZAR 500, reject that trade and show the reason.
- Replay remains simulated and does not submit MT5 broker orders. Performance from historical data does not establish future profitability.

## Implementation checkpoint (2026-11-19)
- Added `backtesting/two_market_replay.py` as an **offline, caller-supplied signal** historical trade/event simulator. It does not yet generate ICT/SMC signals, download MT5 history, compute account margin, display chart playback, mark open-position equity to market, or train parameters. Its current target flag checks ending realized balance only. No demo/live broker order submission.
- Added `backtesting/tests/test_two_market_replay.py` for basic fill chronology, ambiguous stop-first candles, minimum-lot rejection, symbol scope and combined position cap. Tests have been committed but **not executed in this environment**.
- The simulator requires an explicit ZAR-per-price-unit-per-lot conversion for each symbol, spread, slippage, broker lot limits and commission. Do not run with invented broker specs and call the results realistic.
- Next required integration: source-reviewed causal signal_fn, MT5 history importer, actual contract/currency conversion, shared portfolio risk checks including POI budgets and daily mark-to-market loss, reproducible January data replay, browser visualization and walk-forward holdout tests.
- Windows checkout: `git status --short`, then (only if safe) `git pull --ff-only origin codex/xauusd-market-data-safety`, then `python -m pytest backtesting/tests/test_two_market_replay.py -q`. Fix any failures before using results.

## Integration checkpoint — additional code, not a validated full strategy
- `market_data/mt5_history.py` and `backtesting/export_mt5_history.py`: read-only MT5 EURUSD/XAUUSD D1/H4/H1/M15 history export, with broker symbol metadata verification.
- `backtesting/multitimeframe_candidate.py`: closed-bar research-only multi-timeframe adapter using existing top-down and sweep/MSS/FVG scanners; connected via `--strategy multitimeframe --data-dir ...`. This is **not** the full source-approved strategy and has no validated news/session/margin gates.
- `backtesting/replay_viewer.py`: offline browser candle replay with event markers; not a live MT5 trading board.
- `backtesting/walk_forward_research.py`: fixed-rule sweep lookback selection on validation and subsequent test; not autonomous learning, and not yet connected to main replay CLI.
- Added integration tests, **not executed on local Windows or by this GitHub editing environment**.
- Blocking gaps before calling the backtest complete: verified broker historical datasets and cost/contract/FX specs; reliable news exclusions; broker margin validation; realistic open-equity mark-to-market and target milestone; fully chronological multi-symbol event timing; partial exits and POI risk aggregation; independent source validation; full regression test suite; out-of-sample performance reports.
- Do not activate demo/live MT5 orders. Do not represent a replay or simulated R500-to-R20,000 goal as achieved.
