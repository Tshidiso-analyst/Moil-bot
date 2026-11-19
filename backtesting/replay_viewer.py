"""Build a standalone offline historical replay viewer from CSV and event JSON.

This is a visualizer of *simulated* fills, not an MT5 execution terminal.
No web server, credentials, network requests or external JS dependencies.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import pandas as pd


def build_viewer(eurusd_csv, gold_csv, ledger_json, output_html):
    ledger = json.loads(Path(ledger_json).read_text(encoding="utf-8"))
    datasets = {}
    for symbol, path in (("EURUSD", eurusd_csv), ("XAUUSD", gold_csv)):
        frame = pd.read_csv(path)
        required = {"timestamp", "open", "high", "low", "close"}
        if not required <= set(frame.columns):
            raise ValueError(f"{symbol}: missing OHLC/timestamp columns")
        frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
        datasets[symbol] = [
            {"t": int(row.timestamp.timestamp()), "o": float(row.open),
             "h": float(row.high), "l": float(row.low), "c": float(row.close)}
            for row in frame.sort_values("timestamp").itertuples(index=False)
        ]
    payload = json.dumps({"candles": datasets, "ledger": ledger},
                         allow_nan=False).replace("<", "\\u003c")
    template = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Moil-bot historical replay</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{background:#0b1726;color:#edf5ff;font:14px Arial;margin:20px}
section{background:#14263b;padding:14px;border-radius:8px;margin:12px 0}
button,select,input{padding:8px;margin:4px;background:#263e58;color:white;border:1px solid #557}
canvas{width:100%;height:390px;background:#0a1422;border-radius:6px}
table{width:100%;border-collapse:collapse}th,td{padding:7px;border-bottom:1px solid #334;text-align:left}
small{color:#b8cce1}</style></head><body>
<h2>Moil-bot — Historical Trade Replay</h2>
<p><strong>SIMULATED HISTORICAL FILLS — NO MT5 ORDERS</strong></p>
<section><label>Market <select id="symbol"><option>EURUSD</option><option>XAUUSD</option></select></label>
<button id="back">◀ Step</button><button id="play">Play</button><button id="forward">Step ▶</button>
<label>Speed <select id="speed"><option value="1">1×</option><option value="5">5×</option><option value="20">20×</option></select></label>
<input type="range" id="seek" min="0" value="0" style="width:50%">
<p id="status"></p></section>
<section><canvas id="chart" width="1200" height="390"></canvas><small>Visible candles and trade markers are limited to the selected replay point. Green/red candles, blue OPEN markers, yellow CLOSE markers.</small></section>
<section><h3>Virtual account</h3><p id="balance"></p><h3>Events up to selected candle</h3>
<table><thead><tr><th>UTC</th><th>Market</th><th>Action</th><th>Side</th><th>Reason</th><th>Net P/L (ZAR)</th></tr></thead><tbody id="events"></tbody></table></section>
<script id="replay-data" type="application/json">__PAYLOAD__</script>
<script>
const data=JSON.parse(document.getElementById('replay-data').textContent);
const $=id=>document.getElementById(id);
let index=0,playing=false,timer=null;
function current(){return data.candles[$('symbol').value]||[]}
function draw(){
 const bars=current();if(!bars.length){$('status').textContent='No candles';return}
 index=Math.max(0,Math.min(index,bars.length-1));
 $('seek').max=bars.length-1;$('seek').value=index;
 const selected=bars[index],cutoff=selected.t;
 const relevant=data.ledger.events.filter(e=>Date.parse(e.time)/1000<=cutoff);
 const latestClose=[...relevant].reverse().find(e=>e.action==='CLOSE');
 $('status').textContent=new Date(cutoff*1000).toISOString()+' | '+$('symbol').value+' | candle '+(index+1)+'/'+bars.length;
 $('balance').textContent='Starting: R'+data.ledger.starting_zar+' | Last closed trade balance: R'+(latestClose?latestClose.balance_zar:data.ledger.starting_zar)+' | Target: R20,000 (not guaranteed)';
 $('events').innerHTML=relevant.slice(-60).reverse().map(e=>'<tr>'+[
 e.time,e.symbol,e.action,e.side||'',e.reason||'',e.net_pnl_zar??''
 ].map(v=>'<td>'+String(v).replaceAll('&','&amp;').replaceAll('<','&lt;')+'</td>').join('')+'</tr>').join('');
 const canvas=$('chart'),ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;
 ctx.clearRect(0,0,w,h);
 const visible=bars.slice(Math.max(0,index-99),index+1);
 const low=Math.min(...visible.map(b=>b.l)),high=Math.max(...visible.map(b=>b.h));
 const range=Math.max(high-low,1e-9),xstep=w/Math.max(visible.length,1);
 const y=p=>20+(high-p)/range*(h-40);
 visible.forEach((b,j)=>{
   const x=(j+.5)*xstep,up=b.c>=b.o;
   ctx.strokeStyle=up?'#48d7a1':'#f36c77';ctx.fillStyle=ctx.strokeStyle;
   ctx.beginPath();ctx.moveTo(x,y(b.h));ctx.lineTo(x,y(b.l));ctx.stroke();
   ctx.fillRect(x-Math.max(1,xstep*.25),Math.min(y(b.o),y(b.c)),Math.max(2,xstep*.5),Math.max(1,Math.abs(y(b.c)-y(b.o))));
 });
 const from=visible[0].t;
 relevant.filter(e=>e.symbol===$('symbol').value&&(e.action==='OPEN'||e.action==='CLOSE'))
 .forEach(e=>{
   const t=Date.parse(e.time)/1000;if(t<from||t>cutoff)return;
   let j=visible.findIndex((b,k)=>b.t<=t&&(k===visible.length-1||visible[k+1].t>t));
   if(j<0)return;
   const price=e.action==='OPEN'?e.entry:e.exit;if(!Number.isFinite(price))return;
   ctx.fillStyle=e.action==='OPEN'?'#5ea8ff':'#ffda6b';
   ctx.beginPath();ctx.arc((j+.5)*xstep,y(price),5,0,Math.PI*2);ctx.fill();
 });
}
$('symbol').onchange=()=>{index=0;draw()};
$('seek').oninput=()=>{index=Number($('seek').value);draw()};
$('back').onclick=()=>{index--;draw()};
$('forward').onclick=()=>{index++;draw()};
$('speed').onchange=()=>{};
$('play').onclick=()=>{
 playing=!playing;$('play').textContent=playing?'Pause':'Play';
 if(timer)clearInterval(timer);
 if(playing)timer=setInterval(()=>{if(index>=current().length-1){playing=false;clearInterval(timer);$('play').textContent='Play';return}index+=Number($('speed').value);draw()},250);
};
draw();
</script></body></html>"""
    Path(output_html).write_text(template.replace("__PAYLOAD__", payload), encoding="utf-8")
    return Path(output_html)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--eurusd", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--out", default="two_market_replay.html")
    args = parser.parse_args(argv)
    print(build_viewer(args.eurusd, args.gold, args.ledger, args.out))


if __name__ == "__main__":
    main()
