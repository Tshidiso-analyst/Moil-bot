# Moil Bot intelligence completion plan

This document tracks the integration work needed to turn the existing research modules into one explainable analysis workflow. It is deliberately explicit about what is implemented and what is not yet connected.

## Current repository foundations

The repository already contains separate modules for:
- ICT/SMC market structure, fair-value gaps, liquidity context, top-down analysis and strategy candidate evaluation.
- Source-aware PDF and saved YouTube transcript retrieval.
- Strategy evidence review and a rule registry that requires human-reviewed evidence.
- Fundamental news ingestion and a basic sentiment summary.
- Alerts, notification delivery, risk limits, trade guards and cost-aware backtesting.
- MT5 read-only market data and a real-time analysis pipeline.

The modules are not yet one fully integrated, validated trading intelligence system. Presence of a module is not evidence that its feature is live in the dashboard.

## This branch

### Added: economic event risk foundation

`fundamentals/event_risk.py` adds a deterministic, provider-independent event model for calendar events such as NFP, CPI and FOMC:
- Requires timezone-aware release times.
- Applies a configurable high-impact blackout (default: 30 minutes before and 15 minutes after).
- Compares actual with forecast only when both are supplied.
- Keeps direction neutral by default. A surprise is not automatically bullish or bearish; callers must explicitly provide an event-specific interpretation mapping.
- Retains source name and URL so the dashboard can show where calendar facts came from.
- Blocks new-trade recommendations during the blackout. It does not close existing positions.

Tests are in `fundamentals/tests/test_event_risk.py`.

### Added in the alert integration increment

`alerts/event_alerts.py` converts caller-supplied high-impact events into warning alerts (upcoming) or critical alerts (inside the blackout window). Alerts are limited to symbols containing the event currency, retain source details, and use a stable event key so repeated scheduler calls do not resend the same alert during one process lifetime. `AlertEngine` stores alerts even when delivery is disabled and suppresses duplicate notifications for a matching key.

### Not yet implemented by these modules

- They do not fetch an economic calendar. A trusted calendar provider or user-supplied event feed must be connected and scheduled by the application.
- They do not persist the alert deduplication index across process restarts; the current alert store is in-memory.
- They do not infer missing actual, forecast, previous, revisions, unemployment, wages, central-bank guidance or market expectations.
- They do not claim a CPI/NFP/FOMC release predicts price direction.
- The dashboard does not yet run a calendar polling/scheduling loop. Until that is implemented, event alerts are a tested integration point, not a live feed.

## Completion workstreams and acceptance criteria

### 1. ICT/SMC strategy intelligence
- Combine higher-timeframe bias, session context, dealing range, premium/discount, liquidity pools and sweeps, BOS/CHoCH, displacement, FVG, order blocks and candle confirmation.
- Make every entry model explicit: setup, trigger, invalidation, stop placement, target selection and no-trade conditions.
- Preserve the user's stated guardrails as configurable preferences: New York session only, wait until one hour after the open, one trade per day, 1% maximum planned risk, and avoid CPI/NFP/PPI/FOMC high-impact release days.
- Never treat a wick as a confirmed BOS when the rule requires a candle-body close.
- A setup remains a research candidate until its exact rule version has source review and out-of-sample backtesting.

Acceptance: deterministic tests cover bullish, bearish, mixed, consolidation, distribution, sweep-without-confirmation, conflicting timeframes, session exclusion and invalidation.

### 2. PDF and video knowledge ingestion
- Keep source metadata, page numbers, video IDs, URLs, transcript language and retrieval timestamps.
- Detect missing, duplicate, scanned/image-only and failed sources without silently marking them learned.
- Search both source types and show citations beside each retrieved passage.
- Separate source retrieval from human approval; a matching phrase must never automatically become a trading rule.

Acceptance: ingestion can be rerun without duplicating records; failures are reported; every reviewed rule points to exact source evidence; tests cover empty, malformed and partial catalogues.

### 3. Fundamentals and event analysis
- Connect a named, configured economic-calendar provider and persist its source, timezone, event importance and update time.
- For NFP, inspect headline payrolls, unemployment, average hourly earnings, revisions and expectations. For CPI, inspect headline/core and monthly/annual rates. For FOMC, inspect the statement, rate decision, projections and press conference.
- Compare actual, forecast, previous and revisions; report what is known, unknown and potentially conflicting.
- Keep the initial reaction separate from the sustained market interpretation. Require price confirmation before changing a technical bias.
- Treat stale or missing calendar data as unverified, not as proof that no event is scheduled.

Acceptance: fixture-based tests cover beats, misses, in-line releases, revisions, stale feeds, missing fields, conflicting components and timezone boundaries.

### 4. Alerts and notifications
- Emit alerts for setup qualification/rejection, session transitions, approaching high-impact events, event blackout start/end, risk-limit warnings and thesis invalidation.
- Deduplicate repeated events and retain alert history even when delivery is disabled.
- Keep email/SMS credentials in environment secrets; test delivery in development mode.
- Never send a notification that describes a trade as executed unless MT5 confirms the fill.

Acceptance: tests cover deduplication, disabled channels, delivery failures, event alerts, alert acknowledgement and resolution.

### 5. Backtesting, risk and MT5 boundaries
- Validate strategy rules with spread, commission, slippage, realistic fills, session constraints and out-of-sample periods.
- Record sample size, expectancy, profit factor, drawdown, exposure and performance by session/event regime.
- Keep the live MT5 service read-only until a separately reviewed execution design, broker-specific sizing validation, demo test suite and explicit approval exist.
- Position sizing must use instrument contract specifications, tick value, tick size, account currency, leverage and margin requirements. Do not estimate lots from price distance alone.
- A backtest result must not silently promote a rule or enable live execution.

Acceptance: no order API is reachable from the analysis dashboard; risk rejection is fail-closed; tests include insufficient history, missing instrument metadata, high spread, news blackout and max-loss breaches.

## Safe implementation order

1. Finish and test the event-calendar provider adapter, then wire its verified status into the trade guard and event alerts.
2. Add a single analysis orchestration result that carries technical, fundamental, calendar, source-evidence and risk explanations.
3. Complete the ICT entry/exit rule specifications and fixture-based tests.
4. Complete PDF/video ingestion health reports and evidence review.
5. Add walk-forward backtest reports and a read-only dashboard view for the combined analysis.
6. Review demo-only execution separately; do not enable real-money execution as part of this workstream.

## Validation status

The GitHub connector can write to the repository, but it cannot run the project's Python test suite in the user's local Windows/MT5 environment. CI should run the tests in a clean Linux environment; MT5-specific checks must be run locally on Windows with a demo terminal. No test pass is claimed by this document.
