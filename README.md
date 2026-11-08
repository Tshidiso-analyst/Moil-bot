# Moil-bot

Moil-bot is a Forex market-analysis and trading-research platform with a locally connected MetaTrader 5 (MT5) dashboard and guarded DEMO order execution.

The project is being developed as a full platform: a web dashboard, a shared analysis and knowledge backend, and future installable desktop/mobile clients. The current repository is not yet a fully autonomous trading system.

> **Trading safety:** broker order execution is intended for verified MT5 DEMO accounts only. REAL, CONTEST and unknown account types must be rejected. Never put broker passwords, API keys or account credentials in Git. Automated tests use fake MT5 objects; they do not prove that a real broker accepted an order.

## Project status

The active development line is `codex/intelligence-foundation`. Pull request [#140](https://github.com/Tshidiso-analyst/Moil-bot/pull/140) is the current draft integration path into `main`. Do not assume the draft PR is production-ready or merge it without reviewing its latest checks and diff.

GitHub Actions run #297 passed **363 tests on Linux and 363 tests on Windows**, including the Windows MT5 package/account-mode checks. Run #300 is verifying the additional hosted authentication database startup guard. These are automated tests, not a broker execution test.

See [docs/PROJECT_ROADMAP.md](docs/PROJECT_ROADMAP.md) for milestones, current status, acceptance criteria and the next work item.
Hosted mode now requires PostgreSQL-backed login sessions, supports login/logout, same-origin POST enforcement and secure cookies. First-user provisioning is documented in [docs/AUTHENTICATION_SETUP.md](docs/AUTHENTICATION_SETUP.md). Public production deployment remains blocked until persistent rate limiting, email verification/recovery, MFA, per-user data isolation, database provisioning and operational review are complete.

## What exists today

| Area | Current capability | Remaining verification |
|---|---|---|
| Dashboard | Local dashboard; hosted mode requires authenticated PostgreSQL-backed sessions | Complete user-flow, per-user isolation and security review |
| MT5 connection | Local terminal connection, account metadata, symbols, candles and positions | Verify on the owner's Windows terminal and broker DEMO account |
| Market analysis | Real-time analysis pipeline and trading decision components | Validate signals against labelled market data |
| ICT/SMC knowledge | PDF/video knowledge search and concept extraction | Ingestion coverage, source quality and traceability |
| Strategy rules | Rule registry separates reviewed evidence from execution approval | Complete human review and rule validation |
| Fundamentals | Economic-calendar provider model, freshness checks and event analysis for NFP, CPI, FOMC and other releases | Configure and verify a real provider; validate coverage and timestamps |
| Alerts | Alert and notification components | Persistence, deduplication and delivery checks |
| DEMO execution | Explicitly confirmed, reviewed-rule DEMO market-order path with broker-based sizing and protective levels | Manual Windows DEMO integration test; no REAL trading |
| Backtesting | Backtesting components exist | Walk-forward evaluation and controlled promotion of candidate rules |
| Clients/deployment | Hosted authentication gate and local-only MT5 boundary implemented | Provision hosted PostgreSQL, complete remaining identity/security controls, and build Windows/mobile clients |

## Architecture map

- `dashboard/` — local dashboard, pages, MT5 live service and real-time pipeline.
- `execution/` — MT5 execution adapter, DEMO start controller and connection diagnostics.
- `strategy/` — trade decisions, rule registry, source review and ICT/SMC qualification logic.
- `risk/` — account and trade risk controls.
- `fundamentals/` — economic calendar providers, event monitoring and release analysis.
- `market_data/` and `analysis/` — market data and analysis services.
- `knowledge/` — PDF/video ingestion, catalogues, extraction and unified search.
- `backtesting/` — historical strategy evaluation components.
- `alerts/` and `notifications/` — alert generation and delivery.
- `chat/` — chat and execution-result integration.
- `docs/` — operational plans, test plans and project roadmap.

## Local development (Windows / PowerShell)

### 1. Clone the development branch

Use a new folder so the existing local copy is preserved until the replacement has been verified:

```powershell
cd C:\Users\vumil
git clone --branch codex/intelligence-foundation --single-branch https://github.com/Tshidiso-analyst/Moil-bot.git Moil-bot-clean
cd .\Moil-bot-clean
```

Do not delete or overwrite the old `C:\Users\vumil\Moil-bot` folder yet. Compare its uncommitted files and local data before migrating anything.

### 2. Create the virtual environment

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

MetaTrader5 is a Windows/local-terminal dependency. A compatible Windows installation of the MT5 terminal is required for broker integration tests. Do not expect MT5 terminal connectivity on a hosted Linux service.

### 3. Configure environment

```powershell
Copy-Item .env.example .env
```

Edit `.env` locally and only add credentials that are required. Never commit `.env`. Keep API keys and MT5 credentials out of source code, screenshots, issue reports and logs.

### 4. Run automated tests

```powershell
python -m pytest -q
```

Run focused tests while working on a subsystem, then run the full suite before committing:

```powershell
python -m pytest execution/tests -q
python -m pytest fundamentals/tests strategy/tests -q
python -m pytest -q
```

### 5. Start the local dashboard

```powershell
python -m dashboard.app
```

Open the local URL printed in the terminal. If using Streamlit in a branch that still has the Streamlit entry point, follow that branch's documented launch command instead.

## MT5 DEMO execution rules

The following are non-negotiable:

1. The broker-reported account mode must be DEMO immediately before an order or close request. A dashboard selection is not proof.
2. REAL, CONTEST, unknown or disconnected accounts are blocked.
3. DEMO order sending requires a separate human-approved DEMO rule and explicit per-order confirmation.
4. Calendar data must be verified and fresh; high-impact event blackouts block new entries.
5. Daily trade count, open positions and daily loss must be successfully verified. Missing or malformed MT5 history must block execution, never be treated as zero.
6. Position sizing must use broker-calculated P/L, broker volume limits and the approved risk budget.
7. Stop loss and take profit are mandatory. The final quote-to-stop loss must remain within the approved cash-risk budget.
8. No unattended or automatic order sending. No REAL-money order execution.

A manual DEMO test must be performed only after the automated suite passes and the DEMO test plan is reviewed. Start with one explicitly confirmed DEMO order and verify the returned ticket, fill, volume, stop loss and take profit in the MT5 terminal.

## Working agreement: how we develop

- GitHub development branch is the source of truth for agreed code changes.
- Work one issue at a time. Each issue must describe the problem, scope, acceptance criteria and tests.
- Keep changes small and review the diff before committing or merging.
- Run focused tests, then the full regression suite.
- Never overwrite local work or secrets when cloning/synchronizing.
- Keep `main` stable; integrate through a reviewed pull request.
- Update the roadmap and relevant issue whenever scope, status or acceptance criteria change.
- A passing test suite does not mean a strategy is profitable or a broker order is safe.

## Current next step

Start with **Milestone 1 — MT5 DEMO execution reliability**. Review the MT5 history, daily-risk and position safeguards and their tests, then complete the documented Windows DEMO integration test. Do not move to autonomous execution; it is not a project goal for this stage.
