"""Read-only XAUUSDm paper-trading viewer. No MT5 order functions are called.

Run: python -m dashboard.paper_trading
Open: http://127.0.0.1:8502
Signals are unvalidated, closed-candle top-down SMC research; no orders.
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from execution.quote_safety import require_fresh_tick
from risk.symbols import canonicalize_symbol
from strategy.smc_research import inspect_smc
from strategy.gold_topdown import inspect_gold_topdown
from dashboard.interactive_gold_chart import chart_panel

SYMBOL = "XAUUSDm"
LOT = 0.01


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
    h1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 120)
    h1_closed = []
    if h1_rates is not None and len(h1_rates) >= 6:
        h1_sorted = sorted(({"time": int(r["time"]), "open": float(r["open"]),
                            "high": float(r["high"]), "low": float(r["low"]),
                            "close": float(r["close"])} for r in h1_rates), key=lambda b: b["time"])
        h1_closed = h1_sorted[:-1]
    def closed_timeframe(timeframe, count=120):
        if timeframe is None:
            return []
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) < 13:
            return []
        ordered = sorted(({"time": int(r["time"]), "open": float(r["open"]),
                           "high": float(r["high"]), "low": float(r["low"]),
                           "close": float(r["close"])} for r in rates), key=lambda b: b["time"])
        return ordered[:-1]

    d1_closed = closed_timeframe(getattr(mt5, "TIMEFRAME_D1", None))
    h4_closed = closed_timeframe(getattr(mt5, "TIMEFRAME_H4", None))
    topdown = inspect_gold_topdown(
        d1_bars=d1_closed, h4_bars=h4_closed,
        h1_bars=h1_closed, m15_bars=closed)
    smc = inspect_smc(closed, htf_bars=h1_closed)
    # Preliminary M15 signals cannot override the D1/H4/H1 research gates.
    if topdown["stage"] != "m15_confirmation":
        smc = {"status": "WAIT", "execution_ready": False,
               "direction": topdown["direction"], "stage": topdown["stage"],
               "reasons": ["Top-down confirmation not complete."], "events": []}
    trades = []  # No fabricated fills from unvalidated research rules.
    risk_budget = min(float(account.balance), float(account.equity)) * .01
    return dict(symbol=symbol, currency=str(getattr(account, "currency", "")),
                bid=float(tick.bid), ask=float(tick.ask), risk_budget=round(risk_budget, 2),
                trades=trades, candles=closed[-80:], smc=smc, topdown=topdown, execution="DISABLED",
                note="Closed-candle D1/H4/H1/M15 research only. No validated entry signals, simulated fills, or broker orders.")


def page(snapshot, error=None):
    esc = html.escape
    if error:
        body = f"<h2>Read-only data unavailable</h2><p>{esc(str(error))}</p>"
    else:
        smc = snapshot["smc"]
        smc_html = ("<h3>SMC research: " + esc(smc["status"]) + "</h3><p>H1 bias: "
                    + esc(smc["direction"]) + " | Stage: " + esc(smc["stage"]) + "</p>"
                    + "".join("<p>" + esc(reason) + "</p>" for reason in smc["reasons"])
                    + "<p>Research only. Order authorization: NO.</p>")
        topdown = snapshot.get("topdown", {})
        topdown_html = ("<h3>Top-down research: " + esc(topdown.get("status", "WAIT")) + "</h3>"
                        + "".join("<p>" + esc(tf) + ": " + esc(details.get("bias", "unknown")) + "</p>"
                                  for tf, details in topdown.get("timeframes", {}).items())
                        + "".join("<p>" + esc(reason) + "</p>" for reason in topdown.get("reasons", [])))
        next_html = ("<h3>What Moil-bot is waiting for</h3>"
                     + "".join("<p>" + esc(message) + "</p>"
                               for message in topdown.get("next_checks", [])))
        level_html = "<h3>Confirmed reference levels (not trade signals)</h3>"
        for tf, details in topdown.get("timeframes", {}).items():
            high = details.get("last_confirmed_swing_high")
            low = details.get("last_confirmed_swing_low")
            if high is not None and low is not None:
                level_html += ("<p>" + esc(tf) + " high: " + f"{high:.3f}"
                               + " | low: " + f"{low:.3f}" + "</p>")
        if not topdown.get("next_checks"):
            next_html += "<p>Waiting for enough valid closed candles to evaluate the setup.</p>"
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
                + "<h3>Gold M15 — live-refreshing closed-candle chart</h3>"
                + chart_panel()
                + topdown_html + level_html + next_html + smc_html +
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
