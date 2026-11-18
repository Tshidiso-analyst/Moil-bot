"""Browser-side interactive XAUUSDm chart, research only.

Uses TradingView Lightweight Charts (not the TradingView website or broker feed).
Chart is initialized from the read-only /snapshot endpoint and refreshed every 5s.
"""
from __future__ import annotations


def chart_panel():
    return r'''<section id="chart-section">
<h3>MOIL GOLD — Interactive M15 chart</h3>
<p>Drag to pan, scroll/pinch to zoom. The last forming candle is intentionally excluded.
Overlays are research references, not trade signals.</p>
<div id="chart-status" role="status">Loading closed-candle gold data...</div>
<div id="gold-chart" style="height:520px;width:100%;position:relative"></div>
<div id="chart-legend">Yellow: confirmed swing highs | Blue: confirmed swing lows | Purple: H4 midpoint | Cyan: Fibonacci levels</div>
</section>
<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
(function () {
  const el = document.getElementById('gold-chart');
  const status = document.getElementById('chart-status');
  if (!window.LightweightCharts) {
    status.textContent = 'Interactive chart library unavailable. Check internet access to unpkg.com.';
    return;
  }
  const chart = LightweightCharts.createChart(el, {
    layout: { background: { type: 'solid', color: '#101b2c' }, textColor: '#c8d7e8' },
    grid: { vertLines: { color: '#1c2c3f' }, horzLines: { color: '#1c2c3f' } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: '#425268' },
    timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#425268' },
    width: el.clientWidth, height: 520
  });
  const candles = chart.addCandlestickSeries({
    upColor: '#24bf92', downColor: '#ec6d7c',
    borderUpColor: '#24bf92', borderDownColor: '#ec6d7c',
    wickUpColor: '#24bf92', wickDownColor: '#ec6d7c'
  });
  let lines = [], first = true, lastData = '';
  const resize = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
  resize.observe(el);
  function addLine(price, title, color, style) {
    if (typeof price !== 'number' || !Number.isFinite(price)) return;
    lines.push(candles.createPriceLine({
      price, title, color, lineWidth: 1,
      lineStyle: style === 'dashed' ? LightweightCharts.LineStyle.Dashed : LightweightCharts.LineStyle.Dotted,
      axisLabelVisible: true
    }));
  }
  function clearLines() {
    for (const line of lines) candles.removePriceLine(line);
    lines = [];
  }
  async function refresh() {
    try {
      const response = await fetch('/snapshot', { cache: 'no-store' });
      if (!response.ok) throw new Error('MT5 snapshot unavailable (' + response.status + ')');
      const payload = await response.json();
      if (payload.error) throw new Error(payload.error);
      const data = payload.data;
      const bars = (data.candles || []).map(b => ({
        time: Number(b.time), open: Number(b.open), high: Number(b.high),
        low: Number(b.low), close: Number(b.close)
      })).filter(b => Number.isFinite(b.time) && [b.open,b.high,b.low,b.close].every(Number.isFinite));
      if (!bars.length) throw new Error('No closed M15 candles available');
      bars.sort((a,b) => a.time - b.time);
      const key = bars.map(b => [b.time,b.open,b.high,b.low,b.close].join(':')).join('|');
      if (key !== lastData) {
        candles.setData(bars);
        lastData = key;
        if (first) { chart.timeScale().fitContent(); first = false; }
      }
      clearLines();
      const tf = (data.topdown || {}).timeframes || {};
      for (const name of ['D1','H4','H1']) {
        const item = tf[name] || {};
        addLine(item.last_confirmed_swing_high, name + ' swing high', '#f5c56d', 'dashed');
        addLine(item.last_confirmed_swing_low, name + ' swing low', '#6ba8fa', 'dashed');
      }
      const range = (data.topdown || {}).h4_range;
      if (range && Number.isFinite(range.midpoint)) {
        addLine(range.midpoint, 'H4 50%', '#c6a0f7', 'dashed');
        if (Number.isFinite(range.high) && Number.isFinite(range.low) && range.high > range.low) {
          for (const ratio of [0.236, 0.382, 0.618, 0.705, 0.786]) {
            addLine(range.low + (range.high - range.low) * ratio,
              'H4 Fib ' + ratio, '#55c9d5', 'dotted');
          }
        }
      }
      status.textContent = 'XAUUSDm | ' + bars.length + ' closed M15 candles | last closed bar: ' +
        new Date(bars[bars.length-1].time * 1000).toLocaleString() +
        ' | Bid ' + data.bid + ' / Ask ' + data.ask + ' | Orders DISABLED';
    } catch (err) {
      status.textContent = 'Chart data not updated: ' + err.message;
    }
  }
  refresh();
  setInterval(refresh, 5000);
})();
</script>''';
