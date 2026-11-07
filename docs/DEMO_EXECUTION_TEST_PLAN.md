# Moil-bot MT5 DEMO execution test plan

## Scope and safety

Moil-bot can submit market orders only after the connected MT5 terminal reports
`ACCOUNT_TRADE_MODE_DEMO`. The dashboard's selected mode is not trusted as
proof of account type. The account type is checked again immediately before
every order and close request.

- REAL and unknown account modes are blocked by the execution adapter.
- The legacy orchestrator is analysis-only and cannot submit orders.
- Orders require a reviewed strategy rule with explicit
  `demo_execution_enabled` approval.
- Approval requires the exact phrase `ENABLE DEMO EXECUTION` and never sets
  `execution_enabled` for real-money execution.
- Demo order placement is restricted to the local computer.
- The strategy order path requires a verified, fresh economic calendar,
  no active high-impact event, no trade already opened today, no existing
  open position, and a daily loss below 1%.
- Position size is calculated with MT5 `order_calc_profit`, broker lot limits,
  and a maximum planned risk of 0.5% per trade.
- Every market order requires a stop loss, take profit, and a separate
  confirmation checkbox. No automatic order loop is started.

## Windows setup

1. Install MetaTrader 5 and log in to a broker-provided DEMO account.
2. Open the intended instrument in Market Watch and confirm that live quotes
   and M15/H1 history are available.
3. From PowerShell in the repository root, activate the project environment
   and install the project dependencies:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Run compilation and automated tests:

   ```powershell
   python -m compileall -q .
   python -m pytest -q --ignore=execution/mt5_connection_test.py --ignore=execution/demo_trade_smoke_test.py
   ```

5. Start the dashboard:

   ```powershell
   python -m dashboard.app
   ```

6. Open `http://127.0.0.1:8501`. Connect using the DEMO option and the
   demo account's login, password, and exact broker server name. If MT5 reports
   a REAL, CONTEST, or unknown account type, the DEMO connection is rejected.

## Demo forward-test procedure

1. Confirm the dashboard shows the account type as DEMO.
2. Open Strategy and inspect the human-reviewed rule and its cited source
   passages. Do not approve a rule whose evidence or conditions you have not
   checked.
3. In **Approve a rule for DEMO forward-testing**, select the reviewed rule
   and type exactly `ENABLE DEMO EXECUTION`. This changes only the rule's
   demo approval flag in the local rule registry.
4. Run **ANALYSE DEMO SETUP** first. Confirm the direction, entry, stop loss,
   take profit, reasons, and rule match.
5. Verify the economic calendar status is fresh and coverage-certified. If it
   is unavailable or stale, the order route must remain blocked.
6. Only when you intentionally want a broker demo order, tick the explicit
   confirmation checkbox and press **SEND DEMO MARKET ORDER**.
7. Verify the returned MT5 ticket and then verify the position in the MT5
   terminal's Trade tab. Compare the broker-reported volume, fill price, stop,
   and target with Moil-bot's result.

## Expected negative tests

- Selecting DEMO while connected to a REAL account must fail connection.
- A REAL account must not send or close orders even if the dashboard is
  manipulated to display DEMO.
- An unapproved rule must not submit an order.
- An unverified/stale calendar or any high-impact event scheduled for the
  current local calendar date must block new entries.
- A second trade on the same local day must be blocked.
- An existing open position must block a new strategy entry.
- A stop/target on the wrong side of the live quote must be rejected.
- A volume below/above broker limits or outside the broker lot step must be
  rejected.
- A position whose calculated loss exceeds the 0.5% risk budget must be
  rejected.
- A broker rejection must be shown as rejected; it must never be reported as
  executed.

## What CI does and does not prove

Linux CI runs the complete automated suite. Windows CI installs the pinned
MetaTrader5 Python package, checks its account-mode constants, compiles the
project, and runs the automated suite with fake MT5 objects.

CI does not log into a broker account or place a demo order. The final broker
integration test must be performed manually on a broker DEMO account using the
procedure above. Never use a REAL account for this test.
