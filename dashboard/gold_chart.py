"""Dependency-free read-only gold candle SVG with confirmed structure overlays."""
from __future__ import annotations

import html
import math

from strategy.gold_topdown import confirmed_pivots


def render_gold_chart(candles, *, width=1080, height=440):
    """Render supplied CLOSED candles only; never implies order authorization."""
    bars = list(candles or [])[-80:]
    if len(bars) < 5:
        return '<p>Not enough closed M15 candles for chart.</p>'
    if any(not all(math.isfinite(float(b[k])) for k in ("open", "high", "low", "close")) for b in bars):
        return '<p>Invalid candle data; chart unavailable.</p>'
    top, bottom, left, right = 25, 50, 60, 25
    plot_h = height - top - bottom
    plot_w = width - left - right
    lo = min(float(b["low"]) for b in bars)
    hi = max(float(b["high"]) for b in bars)
    pad = max((hi - lo) * .08, .01)
    lo -= pad
    hi += pad
    y = lambda price: top + (hi - float(price)) / (hi - lo) * plot_h
    step = plot_w / len(bars)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             'role="img" aria-label="Read-only M15 XAUUSDm closed-candle chart with confirmed swing levels" '
             'style="width:100%;height:auto;background:#101b2c;border-radius:8px">']
    for i in range(5):
        price = lo + (hi-lo)*i/4
        yy = y(price)
        parts.append(f'<line x1="{left}" x2="{width-right}" y1="{yy:.2f}" y2="{yy:.2f}" '
                     'stroke="#334255" stroke-width="0.8"/>')
        parts.append(f'<text x="5" y="{yy+4:.2f}" fill="#aebfd1" font-size="12">{price:.2f}</text>')
    for i, b in enumerate(bars):
        x = left + (i + .5) * step
        up = float(b["close"]) >= float(b["open"])
        color = "#35c79a" if up else "#ee6b78"
        parts.append(f'<line x1="{x:.2f}" x2="{x:.2f}" y1="{y(b["high"]):.2f}" '
                     f'y2="{y(b["low"]):.2f}" stroke="{color}" stroke-width="1.5"/>')
        body_top = min(y(b["open"]), y(b["close"]))
        body_height = max(1.2, abs(y(b["open"])-y(b["close"])))
        parts.append(f'<rect x="{x-max(1,step*.32):.2f}" y="{body_top:.2f}" '
                     f'width="{max(2,step*.64):.2f}" height="{body_height:.2f}" fill="{color}"/>')
    pivots = confirmed_pivots(bars)
    for kind, color, dash in (("highs", "#f6c565", "5 4"), ("lows", "#69a9ff", "5 4")):
        for p in pivots[kind][-3:]:
            yy = y(p["price"])
            x1 = left + (p["confirmed_index"] + .5) * step
            parts.append(f'<line x1="{x1:.2f}" x2="{width-right}" y1="{yy:.2f}" '
                         f'y2="{yy:.2f}" stroke="{color}" stroke-dasharray="{dash}" opacity=".8"/>')
            parts.append(f'<text x="{width-right-95}" y="{yy-4:.2f}" fill="{color}" font-size="11">'
                         f'{kind[:-1].upper()} {p["price"]:.2f}</text>')
    parts.append(f'<text x="{left}" y="{height-14}" fill="#aebfd1" font-size="13">'
                 'M15 closed candles | green: up | red: down | dashed: confirmed swing references</text>')
    parts.append('</svg>')
    return ''.join(parts)
