# DEMO execution and backtesting

## Safety boundary

The new execution command is a **manual, explicitly confirmed DEMO smoke test**. It is not live trading and it does not automatically turn research signals into approved strategy rules.

Hard safeguards in `execution/demo_pipeline.py`:

- Refuses every account whose MT5 `trade_mode` is not `ACCOUNT_TRADE_MODE_DEMO`.
- Requires three explicit confirmations: demo order, allowed trading session, and no prohibited high-impact news.
- Caps requested risk at 1% of balance and uses the broker's `order_calc_profit` to calculate the lot size.
- Rounds volume down to the broker's lot step; rejects a trade if the minimum lot would exceed the risk budget.
- Checks stop distance, free margin, broker order validation, and the final MT5 order result.
- Allows only one open position and blocks another Moil-bot entry during the following 24 hours.
- Uses a dedicated magic number so the daily entry check can identify Moil-bot demo deals.

The smoke test does not retrieve or verify an economic calendar. The operator must check the calendar and confirm the session. Never use the confirmation flags as a shortcut.

## Run a DEMO order smoke test (Windows + local MT5)

1. Open the MetaTrader 5 desktop terminal and log in to a **DEMO** account.
2. Confirm the server/account shown in MT5 is the demo account. Enable Algo Trading in the terminal.
3. In PowerShell, activate the Moil-bot virtual environment and install dependencies:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

4. First inspect the symbol and prices in MT5 Market Watch. Use the exact broker symbol (for example, a broker may use `EURUSDm` rather than `EURUSD`).
5. Only after checking the entry, stop, target, session and economic calendar, run an explicitly confirmed demo test:

   ```powershell
   python -m execution.demo_smoke_test --symbol EURUSD --direction bullish --stop-loss 1.09500 --take-profit 1.10500 --risk-percent 1.0 --confirm-demo-order --confirm-session --confirm-no-high-impact-news
   ```

   Replace the sample prices with valid levels for the live quote and exact broker symbol. The example is not a trade recommendation.

If any safeguard fails, the command exits with a clear block reason and does not call `order_send`. A successful result means MT5 accepted that DEMO order; it does not establish strategy profitability. Close the test position manually in MT5 after confirming the ticket and attached SL/TP.

Optional npm wrapper:

```powershell
npm run demo:test -- --symbol EURUSD --direction bullish --stop-loss 1.09500 --take-profit 1.10500 --risk-percent 1.0 --confirm-demo-order --confirm-session --confirm-no-high-impact-news
```

## Run the historical SMC backtest

The backtest reads completed candles from the locally logged-in MT5 terminal. It submits no orders.

```powershell
python -m backtesting.run_mt5 --symbol EURUSD --timeframe M15 --bars 3000 --stop-distance 0.00100 --reward-multiple 2 --spread 0.00010 --slippage 0.00002 --initial-equity 10000 --train-fraction 0.7
```

- `--stop-distance`, `--spread` and `--slippage` are price units, not pips. Set them for the selected instrument and broker.
- The report separates the chronological in-sample train period from the out-of-sample holdout.
- Signals are evaluated only on the candle history available at that time; entries occur at the next candle open.
- The backtest applies a New York cash-session filter after the first NYSE hour, stops taking new signals after 15:45 New York time, and caps entries at one per New York calendar day.
- Costs are deducted from net results; when a candle touches both stop and target, the stop is assumed first.
- Historical high-impact news days are **not** automatically filtered. Add a verified historical calendar filter before using results to judge the strategy.
- The SMC decision logic remains exploratory. This report does not approve a source-linked strategy rule or enable automated execution.

Optional npm wrapper:

```powershell
npm run backtest:mt5 -- --symbol EURUSD --timeframe M15 --bars 3000 --stop-distance 0.00100 --spread 0.00010 --slippage 0.00002
```

## Run the isolated tests

```powershell
python -m pytest -q execution/tests/test_demo_pipeline.py backtesting/tests/test_smc_runner.py backtesting/tests/test_cost_aware_engine.py
```

Or:

```powershell
npm run test:trading
```

GitHub Actions runs these safety and backtest tests on pushes and pull requests. The MT5 smoke test itself must be run on the user's Windows machine with a logged-in DEMO terminal; hosted CI cannot verify a broker connection or place a demo order.
