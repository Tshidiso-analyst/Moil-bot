"""Read-only XAUUSDm paper-trading viewer. No MT5 order functions are called.

Run: python -m dashboard.paper_trading
Open: http://127.0.0.1:8502
Signals are illustrative closed-candle breakouts, NOT validated ICT/SMC entries.
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from execution.quote_safety import require_fresh_tick
from risk.symbols import canonicalize_symbol

SYMBOL = "XAUUSDm"
LOT = 0.01
STOP_DISTANCE = 2.0
REWARD_MULTIPLE = 2.0


def paper_snapshot(mt5, symbol=SYMBOL):
    """Read-only snapshot with illustrative, unexecuted paper trades."""
    canonicalize_symbol(symbol)
    account = mt5.account_info()
    if account is None or getattr(account, "trade_mode", None) != getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", None):
        raise RuntimeError("A verified MT5 DEMO account is required.")
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError("XAUUSDm is unavailable.")
    tick = mt5.symbol_info_tick(symbol)
    require_fresh_tick(tick)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 200)
    if rates is None or len(rates) < 25:
        raise RuntimeError("At least 25 M15 candles are required.")
    # Exclude the last, still-forming candle. Sort defensively.
    bars = sorted(({"time": int(r["time"]), "open": float(r["open"]),
                    "high": float(r["high"]), "low": float(r["low"]),
                    "close": float(r["close"])} for r in rates), key=lambda b: b["time"])
    closed = bars[:-1]
    trades = []
    active = None
    for i in range(20, len(closed)):
        bar = closed[i]
        if active is not None:
            # Conservative intrabar assumption: stop is hit first if both levels touched.
            stop_hit = bar["low"] <= active["stop"] if active["side"] == "BUY" else bar["high"] >= active["stop"]
            target_hit = bar["high"] >= active["target"] if active["side"] == "BUY" else bar["low"] <= active["target"]
            if stop_hit or target_hit:
                exit_price = active["stop"] if stop_hit else active["target"]
                order_type = mt5.ORDER_TYPE_BUY if active["side"] == "BUY" else mt5.ORDER_TYPE_SELL
                pnl = mt5.order_calc_profit(order_type, symbol, LOT, active["entry"], exit_price)
                active.update(exit=exit_price, exit_time=bar["time"], pnl=round(float(pnl), 2) if pnl is not None and math.isfinite(float(pnl)) else None,
                              status="STOP" if stop_hit else "TARGET")
                trades.append(active)
                active = None
        if active is not None:
            continue
        previous = closed[i-20:i]
        upper = max(b["high"] for b in previous)
        lower = min(b["low"] for b in previous)
        side = "BUY" if bar["close"] > upper else "SELL" if bar["close"] < lower else None
        if side:
            # Illustrative next-bar open, never enter at a previously known close.
            if i + 1 >= len(closed):
                continue
            entry_bar = closed[i+1]
            entry = entry_bar["open"]
            stop = entry - STOP_DISTANCE if side == "BUY" else entry + STOP_DISTANCE
            target = entry + STOP_DISTANCE * REWARD_MULTIPLE if side == "BUY" else entry - STOP_DISTANCE * REWARD_MULTIPLE
            active = dict(side=side, entry=entry, stop=stop, target=target,
                          entry_time=entry_bar["time"], status="OPEN (PAPER)")
    if active:
        trades.append(active)
    risk_budget = min(float(account.balance), float(account.equity)) * .01
    return dict(symbol=symbol, currency=str(getattr(account, "currency", "")),
                bid=float(tick.bid), ask=float(tick.ask), risk_budget=round(risk_budget, 2),
                trades=trades[-30:], candles=closed[-80:], execution="DISABLED",
                note="Illustrative M15 breakout replay; not validated ICT/SMC, not a live strategy or executable signal. "
                     "Historical replay omits spread, slippage and commission. No broker orders.")


def page(snapshot, error=None):
    esc = html.escape
    if error:
        body = f"<h2>Read-only data unavailable</h2><p>{esc(str(error))}</p>"
    else:
        rows = "".join(
            "<tr>" + "".join(f"<td>{esc(str(t.get(k, '-')))}</td>" for k in
            ("side", "entry_time", "entry", "stop", "target", "status", "pnl")) + "</tr>"
            for t in reversed(snapshot["trades"])
        )
        body = (f"<h2>{esc(snapshot['symbol'])} — paper replay</h2>"
                f"<p>Bid: {snapshot['bid']:.3f} | Ask: {snapshot['ask']:.3f} | "
                f"1% risk budget: {snapshot['risk_budget']:.2f} {esc(snapshot['currency'])}</p>"
                f"<p><strong>MT5 ORDERS: DISABLED</strong></p>"
                f"<p>{esc(snapshot['note'])}</p>"
                "<table><tr><th>Side</th><th>Entry UTC</th><th>Entry</th><th>Stop</th>"
                "<th>Target</th><th>Status</th><th>Gross P/L</th></tr>"
                + rows + "</table>"
                "<p>Times are Unix UTC seconds. Refresh to read the latest closed candles.</p>")
    return ("""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="30"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Moil-bot paper trading</title><style>
body{font:16px Arial;background:#0b1726;color:#eaf4ff;padding:24px}
table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #304457;padding:10px;text-align:left}
p{line-height:1.5}strong{color:#ffcd80}</style></head><body>""" + body + "</body></html>").encode("utf-8")


def main():
    import MetaTrader5 as mt5
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/", "/snapshot"):
                self.send_error(404)
                return
            error = None
            snapshot = None
            if not mt5.initialize():
                error = f"MT5 initialization failed: {mt5.last_error()}"
            else:
                try:
                    snapshot = paper_snapshot(mt5)
                except (RuntimeError, ValueError, TypeError) as exc:
                    error = str(exc)
                finally:
                    mt5.shutdown()
            payload = (json.dumps({"error": error, "data": snapshot}).encode("utf-8")
                       if self.path == "/snapshot" else page(snapshot, error))
            self.send_response(503 if error else 200)
            self.send_header("Content-Type", "application/json" if self.path == "/snapshot" else "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
    print("Read-only paper viewer: http://127.0.0.1:8502")
    ThreadingHTTPServer(("127.0.0.1", 8502), Handler).serve_forever()


if __name__ == "__main__":
    main()
