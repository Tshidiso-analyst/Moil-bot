# Moil-bot Project Roadmap

Last reviewed: 2026-11-08  
Active development branch: `codex/intelligence-foundation`  
Current integration PR: [#140](https://github.com/Tshidiso-analyst/Moil-bot/pull/140)

This is the project's progress ledger. Update it whenever an issue is started, completed, blocked or re-scoped. The README is the entry point; this roadmap records what remains and the order in which it should be done.

## Product goal

Build Moil-bot as a complete, modular Forex analysis platform with:
- Market data and technical/ICT/SMC analysis.
- Fundamentals and economic-event awareness (including NFP, CPI and FOMC).
- A searchable, source-linked PDF/video knowledge base.
- Human-reviewed strategy rules and reproducible backtesting.
- Risk controls, alerts and notifications.
- A local MT5 connection and explicitly confirmed DEMO execution.
- A shared backend that can later support web, Windows desktop and mobile clients.

Moil-bot is not currently a fully autonomous trader. Candidate rules must be evidence-backed, human-reviewed, tested and separately approved. REAL-money execution is out of scope and must remain blocked.

## Milestones and tracked issues

The milestone sequence below is mirrored by the GitHub issues linked in each section. Keep the issue status and this document synchronized.

### M0 — Repository control and repeatable development
**GitHub tracking:** [Issue #141](https://github.com/Tshidiso-analyst/Moil-bot/issues/141)  
**Status: In progress**

- [x] Confirm active development branch and current draft integration PR.
- [x] Record the reported local regression result (341 passed, 2026-11-08).
- [x] Add project README and roadmap to the active development branch.
- [ ] Reconcile the development branch, PR #140 and stable `main`.
- [ ] Create a clean clone in a new local folder without deleting the old local copy.
- [ ] Verify environment setup, full tests and dashboard launch from the clean clone.
- [ ] Audit tracked backup files, generated data and local-only configuration before cleanup/migration.

**Exit criteria:** a clean clone can be installed, tested and launched using documented instructions; the active branch and PR relationship are unambiguous; the old local folder is preserved until migration is verified.

### M1 — MT5 DEMO execution and risk reliability
**GitHub tracking:** [Issue #142](https://github.com/Tshidiso-analyst/Moil-bot/issues/142), [Issue #143](https://github.com/Tshidiso-analyst/Moil-bot/issues/143)  
**Status: Automated safeguards are present; audit and manual broker verification remain. Priority: highest.**

- [x] Isolate the MT5 connection diagnostic behind an explicit `main()` entry point so pytest collection does not connect to a terminal.
- [x] Make execution-path open-position lookup fail closed when MT5 is disconnected or returns an error.
- [x] Make daily deal-history and daily-loss checks fail closed on missing history or invalid aggregate values.
- [x] Require DEMO account verification in the execution adapter before trading operations.
- [x] Require explicit order confirmation, approved DEMO rule, protective SL/TP and broker-based risk sizing.
- [ ] Audit all order, close, modify and retry paths for account-mode re-verification and ambiguous broker responses.
- [ ] Add/confirm tests for MT5 `None`, exceptions, malformed history, account changes, duplicate submissions and partial fills.
- [ ] Confirm daily trade counting semantics for entries, reversals, partial fills and broker-server/local-day boundaries.
- [ ] Verify daily loss calculation against MT5 history, commissions, swaps, fees and floating P/L.
- [ ] Ensure dashboard summary/read-only paths never present unavailable MT5 position data as a verified zero.
- [ ] Complete one controlled Windows broker DEMO integration test using [DEMO_EXECUTION_TEST_PLAN.md](DEMO_EXECUTION_TEST_PLAN.md).

**Current audit notes:** `positions()`, `today_entry_count()` and `today_loss_percent()` raise when their required MT5 reads fail. `open_trade_count()` uses the fail-closed `positions()` method. However, `open_trade_summary()` currently substitutes an empty list when disconnected, which can make a display summary look like zero positions; this needs explicit unavailable-state handling. The history window uses the Windows host's local midnight, so broker-server timezone/day-boundary behaviour still needs verification.

**Exit criteria:** all unverifiable risk facts block execution; tests pass on Windows and Linux; a manual DEMO test records a broker-confirmed ticket and protective levels. No REAL, CONTEST, unknown or disconnected account can execute.

### M2 — Fundamentals and economic calendar
**GitHub tracking:** [Issue #144](https://github.com/Tshidiso-analyst/Moil-bot/issues/144)  
**Status: Provider and analysis foundation implemented; real provider verification outstanding.**

- [x] Provider-independent economic event model.
- [x] Generic HTTPS JSON adapter and optional FMP adapter.
- [x] Freshness, coverage and event-impact validation.
- [x] NFP/CPI/FOMC descriptive release analysis.
- [ ] Configure a licensed provider locally without committing credentials.
- [ ] Verify actual provider timestamps, coverage windows, currencies, impact classification and missing-event behaviour.
- [ ] Add holiday/session awareness and explicit timezone tests.
- [ ] Add revision history and richer FOMC/NFP/CPI component handling where provider data supports it.
- [ ] Keep macro bias unverified until a separately validated method and price confirmation exist.

**Exit criteria:** provenance, freshness and coverage are visible; unavailable or uncertain data cannot approve an entry; event analysis does not invent missing values.

### M3 — ICT/SMC strategy intelligence
**GitHub tracking:** [Issue #145](https://github.com/Tshidiso-analyst/Moil-bot/issues/145)  
**Status: Research and decision components exist; automated evidence detectors need validation.**

- [ ] Define deterministic, testable definitions for liquidity pools/sweeps, BOS body close, CHoCH, FVG, order blocks, equilibrium/OTE, displacement and session windows.
- [ ] Build labelled chart examples and unit tests for each detector.
- [ ] Validate multi-timeframe context, New York session timing and daylight-saving transitions.
- [ ] Wire detector outputs into the entry-confirmation checklist.
- [ ] Add explicit no-trade conditions: weak/ambiguous structure, stale data, conflicting signals, high spread, event blackout and outside approved sessions.
- [ ] Make strategy output explanatory: evidence, invalidation, entry, stop, target and rejection reasons.
- [ ] Require human review before a rule can be enabled for DEMO forward-testing.

**Exit criteria:** a setup can be reproduced from historical candles, with source evidence and clear reasons for both acceptance and rejection.

### M4 — PDF/video knowledge and source governance
**GitHub tracking:** [Issue #146](https://github.com/Tshidiso-analyst/Moil-bot/issues/146)  
**Status: Ingestion and unified search exist; coverage and governance work remains.**

- [ ] Inventory source files, transcripts, catalogues and redistribution/licensing metadata.
- [ ] Make ingestion repeatable and idempotent; report failed, skipped and duplicate sources.
- [ ] Preserve PDF page and video timestamp/source links for every extracted claim.
- [ ] Improve retrieval tests for ICT/SMC, sessions, candlesticks, risk, margin and fundamentals.
- [ ] Require human review and evidence IDs before a source can support an executable rule.
- [ ] Track source versions and stale/withdrawn material.
- [ ] Document generated, ignored and intentionally committed data directories.

**Exit criteria:** every strategy claim can be traced to a source and location; ingestion reports coverage and errors; no unreviewed content enables execution.

### M5 — Backtesting and strategy evaluation
**GitHub tracking:** [Issue #147](https://github.com/Tshidiso-analyst/Moil-bot/issues/147)  
**Status: Components exist; validated research workflow not complete.**

- [ ] Define a realistic backtest contract including spread, commission, swap, slippage and execution timing.
- [ ] Prevent look-ahead bias and data leakage.
- [ ] Add in-sample, validation and out-of-sample splits plus walk-forward tests.
- [ ] Report drawdown, expectancy, win rate, profit factor, risk of ruin and trade distribution.
- [ ] Compare strategy versions against a baseline and retain reproducible run metadata.
- [ ] Define minimum sample size and promotion criteria.
- [ ] Allow backtests to propose candidate rules only; never auto-approve rules or send orders.

**Exit criteria:** strategy performance can be independently reproduced and compared; no strategy is promoted based on a single attractive backtest.

### M6 — Alerts, dashboard and notifications
**GitHub tracking:** [Issue #148](https://github.com/Tshidiso-analyst/Moil-bot/issues/148)  
**Status: Dashboard, chart, alert and notification components exist; reliability and UX validation remain.**

- [ ] Verify alert conditions against market and calendar events.
- [ ] Persist alert history and deduplicate repeated alerts across restarts.
- [ ] Test delivery failures, retries, preferences and quiet periods.
- [ ] Display source evidence, timestamps, confidence/verification state and invalidation in alerts.
- [ ] Review dashboard authentication, session handling, CSRF protection and local-only order endpoints.
- [ ] Test dashboard behaviour when MT5, calendar, market data or knowledge services are unavailable.

**Exit criteria:** alerts are traceable, deduplicated and reliably delivered; dashboard failure states are explicit and secure.

### M7 — Full platform clients and deployment
**GitHub tracking:** [Issue #149](https://github.com/Tshidiso-analyst/Moil-bot/issues/149)  
**Status: Architecture direction defined; client packaging and production deployment not complete.**

- [ ] Separate shared backend/API services from dashboard presentation.
- [ ] Define authentication, account ownership, data storage and secret-management model.
- [ ] Build responsive/installable web experience.
- [ ] Build Windows desktop client using the shared backend and local MT5 bridge.
- [ ] Build mobile client for monitoring, research and notifications; do not expose broker credentials unnecessarily.
- [ ] Document hosted-mode limitations: cloud service cannot directly access a user's local MT5 terminal.
- [ ] Add deployment, backups, migrations, monitoring and recovery procedures.
- [ ] Complete security and operational review before production release.

**Exit criteria:** supported clients use one documented backend contract; local MT5 execution stays on the user's trusted Windows machine; deployment and recovery are tested.

## Work order

1. Finish M0 repository alignment and clean-clone validation.
2. Complete M1 before attempting any broker DEMO order.
3. Validate M2 calendar inputs before connecting event analysis to entry qualification.
4. Complete M3 detector validation and M4 source traceability before promoting strategy rules.
5. Build M5 evaluation before claiming a strategy learns or improves.
6. Stabilize M6 before relying on alerts for operational decisions.
7. Build M7 clients and deployment only on a stable backend contract.

## Definition of done for every issue

- Scope and acceptance criteria are written before implementation.
- A focused regression test covers the changed behaviour.
- Relevant full test suite passes.
- Failure modes are tested, not just the happy path.
- Documentation and this roadmap are updated.
- Git diff is reviewed; no credentials, generated secrets or unrelated files are included.
- Work is committed to the active feature branch and integrated through a reviewed PR.
- For trading changes, REAL/CONTEST/unknown account blocking and fail-closed behaviour are explicitly tested.

## Current checkpoint

**Next task:** finish M0 branch/PR reconciliation and clean-clone verification, then work Issue #142 (M1 MT5 risk-history and execution-path audit). Keep the old local folder untouched until the clean clone passes tests and its required local data/configuration has been migrated safely.

Do not submit an MT5 DEMO order until Issue #142 is closed and the preconditions in Issue #143 and `docs/DEMO_EXECUTION_TEST_PLAN.md` are satisfied.
