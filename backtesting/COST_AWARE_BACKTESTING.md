# Cost-aware historical backtester

This is an additive engine. It does not replace `backtesting/engine.py`, invent a strategy, or execute broker orders.

## Minimal use

```python
from backtesting.cost_aware_engine import CostAwareBacktestEngine


def reviewed_signal(history):
    """Return bullish, bearish, or None using only this historical prefix."""
    # Add your explicitly reviewed entry conditions here.
    # Do not use future rows or future-dependent indicator values.
    return None

engine = CostAwareBacktestEngine()
result = engine.run(
    historical_candles,  # timestamp/open/high/low/close columns required
    symbol="EURUSD",
    signal_fn=reviewed_signal,
    stop_distance=0.0010,  # absolute price units, not a percent
    reward_multiple=2.0,
    spread=0.0001,          # full spread in price units
    slippage=0.00005,       # adverse slippage per side
    commission_per_unit_per_side=0.0,
    position_size=1.0,
)

print(result.total_net_profit)
print(result.win_rate, result.profit_factor)
print(result.max_drawdown, result.max_drawdown_pct)
```

## Chronological holdout

```python
split = engine.run_train_test(
    historical_candles,
    "EURUSD",
    reviewed_signal,
    train_fraction=0.70,
    stop_distance=0.0010,
    reward_multiple=2.0,
    spread=0.0001,
    slippage=0.00005,
)
print("Train net:", split.train.total_net_profit)
print("Out-of-sample net:", split.test.total_net_profit)
```

The test callback can use earlier candles for indicator warm-up, but new test trades cannot start before the held-out segment. The engine sends a copy of the historical prefix through each signal time and enters on the following candle's open.

## Execution assumptions and limitations

- OHLC values are treated as reference/mid prices. Spread and slippage are applied adversely on each side; commission is charged for both sides.
- If the same candle touches both stop and target, the stop is assumed first because OHLC alone cannot reveal the intra-candle path.
- A gap through a stop is exited at the adverse opening price. An open position at the end of a segment is closed at that segment's final close.
- `profit_factor` is `None` when no losing trades exist because the ratio is undefined.
- P&L is reported for the supplied position size and modeled units. Contract size, account-currency conversion, swap/financing, partial fills, variable spreads, and broker-specific execution require additional modeling as applicable.
- A fixed train/test split is not walk-forward validation and does not prevent strategy overfitting on its own.
- This module neither approves source rules nor enables live execution. Keep broker order submission disabled until separate validation and operational safeguards are complete.
