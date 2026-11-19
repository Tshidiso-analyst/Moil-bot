"""Offline two-symbol historical replay. NO MetaTrader5 import or order submission.

Input candles are UTC timestamped CLOSED bars at the same timeframe. Each
instrument's price-unit P/L conversion must be supplied explicitly in ZAR.
Signals are caller-supplied research hypotheses, NOT validated ICT detectors.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timezone
from zoneinfo import ZoneInfo
import json
import math
from pathlib import Path

import pandas as pd

SYMBOLS = frozenset({"EURUSD", "XAUUSD"})
NY = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class Instrument:
    symbol: str
    spread: float
    slippage: float
    zar_per_price_unit_per_lot: float
    min_lot: float
    lot_step: float
    max_lot: float
    commission_zar_per_lot_per_side: float = 0.0


def _validate_instrument(spec):
    if spec.symbol not in SYMBOLS:
        raise ValueError("Only EURUSD and XAUUSD are supported")
    for field in ("spread", "slippage", "commission_zar_per_lot_per_side"):
        if not math.isfinite(getattr(spec, field)) or getattr(spec, field) < 0:
            raise ValueError(f"Invalid {field}")
    for field in ("zar_per_price_unit_per_lot", "min_lot", "lot_step", "max_lot"):
        if not math.isfinite(getattr(spec, field)) or getattr(spec, field) <= 0:
            raise ValueError(f"Invalid {field}")
    if spec.max_lot < spec.min_lot:
        raise ValueError("max_lot below min_lot")


def _bars(frame):
    needed = {"timestamp", "open", "high", "low", "close"}
    if not needed.issubset(frame.columns):
        raise ValueError("Missing timestamp/OHLC columns")
    data = frame.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="raise")
    if data["timestamp"].isna().any() or data["timestamp"].duplicated().any():
        raise ValueError("Missing or duplicate timestamps")
    data = data.sort_values("timestamp").reset_index(drop=True)
    for name in ("open", "high", "low", "close"):
        data[name] = pd.to_numeric(data[name], errors="raise")
        if not data[name].map(math.isfinite).all():
            raise ValueError("Nonfinite OHLC")
    if ((data.high < data[["open", "close", "low"]].max(axis=1)) |
        (data.low > data[["open", "close", "high"]].min(axis=1)) |
        (data.low <= 0)).any():
        raise ValueError("Invalid OHLC")
    return data


def replay(
    candles: dict[str, pd.DataFrame],
    instruments: dict[str, Instrument],
    signal_fn,
    *,
    starting_zar: float = 500.0,
    start: str = "2026-01-01T00:00:00Z",
    risk_fraction: float = 0.02,
    daily_loss_fraction: float = 0.05,
    max_daily_entries: int = 10,
    max_open: int = 3,
    max_portfolio_risk_fraction: float = 0.03,
    reward_multiple: float = 2.0,
):
    """Simulate next-open fills and stop/target exits, with one shared account.

    signal_fn(symbol, closed_history) -> None or {side: 'buy'|'sell',
    stop: absolute price, target: absolute price}. No future rows supplied.
    Candle timestamps represent bar OPEN time. Signals evaluated at bar i
    close and scheduled for bar i+1 open; next bar time must be later.
    Daily-loss halt uses realized P/L relative to NY-day starting balance.
    """
    if not math.isfinite(starting_zar) or starting_zar <= 0:
        raise ValueError("starting_zar must be positive")
    if not 0 < risk_fraction <= 0.02 or not 0 < daily_loss_fraction <= 1:
        raise ValueError("Invalid risk fractions")
    if not 0 < max_portfolio_risk_fraction <= 1 or reward_multiple <= 0:
        raise ValueError("Invalid portfolio risk or reward")
    if max_open < 1 or max_daily_entries < 1:
        raise ValueError("Invalid position limits")
    if not candles or not set(candles) <= SYMBOLS or not set(instruments) <= SYMBOLS:
        raise ValueError("Only EURUSD and XAUUSD are supported")
    if set(candles) != set(instruments):
        raise ValueError("Supply matching EURUSD/XAUUSD data and instruments")
    if not callable(signal_fn):
        raise ValueError("signal_fn must be callable")
    prepared = {s: _bars(f) for s, f in candles.items()}
    for s, spec in instruments.items():
        _validate_instrument(spec)
        if spec.symbol != s:
            raise ValueError("Instrument symbol mismatch")
    start_ts = pd.Timestamp(start)
    if start_ts.tzinfo is None:
        raise ValueError("start must include timezone")
    balance = float(starting_zar)
    events, positions, closed = [], [], []
    entries_by_day, day_start, day_pnl = {}, {}, {}
    pending = {}
    # All bars must have same timeframe duration per symbol; process ordered opens.
    timeline = sorted((row.timestamp, s, i) for s, df in prepared.items()
                      for i, row in df.iterrows())
    for timestamp, symbol, i in timeline:
        data, spec = prepared[symbol], instruments[symbol]
        bar = data.iloc[i]
        day = timestamp.tz_convert(NY).date()
        if day not in day_start:
            day_start[day] = balance
            day_pnl[day] = 0.0
        # A signal is decided at prior close and may execute at this open.
        request = pending.pop(symbol, None)
        if request is not None and timestamp >= start_ts:
            side, stop, target = request["side"], request["stop"], request["target"]
            mid = float(bar.open)
            entry = mid + (spec.spread / 2 + spec.slippage) * (1 if side == "buy" else -1)
            distance = (entry - stop) if side == "buy" else (stop - entry)
            reward = (target - entry) if side == "buy" else (entry - target)
            reason = None
            if distance <= 0 or reward / distance < reward_multiple:
                reason = "invalid_stop_or_reward"
            elif entries_by_day.get(day, 0) >= max_daily_entries:
                reason = "daily_entry_limit"
            elif len(positions) >= max_open:
                reason = "max_open_positions"
            elif day_pnl[day] <= -daily_loss_fraction * day_start[day]:
                reason = "daily_loss_limit"
            else:
                risk_budget = balance * risk_fraction
                per_lot_loss = distance * spec.zar_per_price_unit_per_lot + 2 * spec.commission_zar_per_lot_per_side
                desired = risk_budget / per_lot_loss
                lots = min(desired, spec.max_lot)
                lots = math.floor((lots + 1e-12) / spec.lot_step) * spec.lot_step
                lots = round(lots, 8)
                if lots + 1e-10 < spec.min_lot:
                    reason = "minimum_lot_exceeds_risk"
                else:
                    reserved = sum(p["risk_zar"] for p in positions)
                    if reserved + lots * per_lot_loss > balance * max_portfolio_risk_fraction + 1e-8:
                        reason = "portfolio_risk_limit"
            if reason:
                events.append(dict(time=timestamp.isoformat(), symbol=symbol, action="REJECT", reason=reason))
            else:
                commission = spec.commission_zar_per_lot_per_side * lots
                balance -= commission
                pos = dict(symbol=symbol, side=side, entry_time=timestamp.isoformat(),
                           entry=entry, stop=stop, target=target, lots=lots,
                           risk_zar=lots * per_lot_loss, opening_commission=commission)
                positions.append(pos)
                entries_by_day[day] = entries_by_day.get(day, 0) + 1
                events.append(dict(time=timestamp.isoformat(), action="OPEN", balance_zar=round(balance, 4), **pos))
        # Evaluate stop/target against this candle. Stop wins on ambiguity.
        for pos in list(positions):
            if pos["symbol"] != symbol:
                continue
            buy = pos["side"] == "buy"
            # Mid OHLC -> executable exit side, conservatively include adverse slippage.
            offset = spec.spread / 2 + spec.slippage
            open_exit = float(bar.open) + (-offset if buy else offset)
            low_exit = float(bar.low) - offset if buy else float(bar.low) + offset
            high_exit = float(bar.high) - offset if buy else float(bar.high) + offset
            stop_hit = low_exit <= pos["stop"] if buy else high_exit >= pos["stop"]
            target_hit = high_exit >= pos["target"] if buy else low_exit <= pos["target"]
            if not (stop_hit or target_hit):
                continue
            if stop_hit:
                gap = open_exit < pos["stop"] if buy else open_exit > pos["stop"]
                exit_price = open_exit if gap else pos["stop"]
                reason = "STOP_GAP" if gap else ("STOP_AMBIGUOUS" if target_hit else "STOP")
            else:
                exit_price = pos["target"]
                reason = "TARGET"
            pnl = (exit_price - pos["entry"]) * (1 if buy else -1) * pos["lots"] * spec.zar_per_price_unit_per_lot
            closing_commission = spec.commission_zar_per_lot_per_side * pos["lots"]
            net = pnl - closing_commission - pos["opening_commission"]
            balance += pnl - closing_commission
            day_pnl[day] += net
            event = dict(time=timestamp.isoformat(), action="CLOSE", symbol=symbol,
                         side=pos["side"], entry_time=pos["entry_time"], entry=pos["entry"],
                         exit=exit_price, lots=pos["lots"], reason=reason,
                         net_pnl_zar=round(net, 4), balance_zar=round(balance, 4))
            events.append(event)
            closed.append(event)
            positions.remove(pos)
        if i < len(data) - 1:
            history = data.iloc[:i + 1].copy(deep=True)
            signal = signal_fn(symbol, history)
            if signal is not None:
                if not isinstance(signal, dict) or signal.get("side") not in ("buy", "sell"):
                    raise ValueError("Signal must be a dict with buy/sell side")
                stop, target = float(signal["stop"]), float(signal["target"])
                if not math.isfinite(stop) or not math.isfinite(target):
                    raise ValueError("Nonfinite signal prices")
                pending[symbol] = dict(side=signal["side"], stop=stop, target=target)
                events.append(dict(time=timestamp.isoformat(), action="SIGNAL", symbol=symbol,
                                   side=signal["side"], stop=stop, target=target))
    return dict(starting_zar=starting_zar, ending_balance_zar=round(balance, 4),
                target_zar=20000, target_reached=balance >= 20000,
                events=events, closed_trades=closed, open_positions=positions,
                note="HISTORICAL SIMULATION ONLY; not MT5 orders. Open positions are not marked to market.")


def save_replay(result, path):
    """Persist auditable simulated event log as JSON."""
    Path(path).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
