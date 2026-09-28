from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from dashboard.charts import create_price_and_volume_chart


HOST = "127.0.0.1"
PORT = 8501


def build_sample_candles() -> list[dict[str, Any]]:
    """Return deterministic demonstration candles for the dashboard UI."""

    return [
        {
            "timestamp": "2026-09-28 09:00",
            "open": 100.0,
            "high": 104.0,
            "low": 98.0,
            "close": 103.0,
            "volume": 1200,
        },
        {
            "timestamp": "2026-09-28 10:00",
            "open": 103.0,
            "high": 107.0,
            "low": 101.0,
            "close": 106.0,
            "volume": 1500,
        },
        {
            "timestamp": "2026-09-28 11:00",
            "open": 106.0,
            "high": 109.0,
            "low": 103.0,
            "close": 104.0,
            "volume": 1350,
        },
        {
            "timestamp": "2026-09-28 12:00",
            "open": 104.0,
            "high": 111.0,
            "low": 103.0,
            "close": 110.0,
            "volume": 1800,
        },
        {
            "timestamp": "2026-09-28 13:00",
            "open": 110.0,
            "high": 114.0,
            "low": 108.0,
            "close": 112.0,
            "volume": 2100,
        },
        {
            "timestamp": "2026-09-28 14:00",
            "open": 112.0,
            "high": 115.0,
            "low": 109.0,
            "close": 111.0,
            "volume": 1600,
        },
    ]


def build_chart_html(symbol: str) -> str:
    candles = build_sample_candles()

    figure = create_price_and_volume_chart(
        candles=candles,
        symbol=symbol,
    )

    return figure.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={
            "responsive": True,
            "displaylogo": False,
        },
    )


def build_dashboard_html(symbol: str = "GBPUSD") -> str:
    chart_html = build_chart_html(symbol)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Moil Bot — Trading Dashboard</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f4f6f8;
            color: #1f2937;
        }}

        header {{
            background: #111827;
            color: white;
            padding: 20px 30px;
        }}

        header h1 {{
            margin: 0 0 5px;
            font-size: 28px;
        }}

        header p {{
            margin: 0;
            color: #d1d5db;
        }}

        main {{
            max-width: 1500px;
            margin: 0 auto;
            padding: 25px;
        }}

        .toolbar {{
            background: white;
            padding: 18px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}

        select {{
            padding: 10px 14px;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            font-size: 15px;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 20px;
        }}

        .card {{
            background: white;
            border-radius: 10px;
            padding: 18px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}

        .card h3 {{
            margin-top: 0;
            font-size: 14px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .value {{
            font-size: 24px;
            font-weight: bold;
        }}

        .section {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}

        .section h2 {{
            margin-top: 0;
        }}

        .details {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }}

        .detail {{
            padding: 14px;
            background: #f9fafb;
            border-radius: 8px;
        }}

        .detail strong {{
            display: block;
            margin-bottom: 5px;
        }}

        .chart {{
            width: 100%;
            overflow: hidden;
        }}

        @media (max-width: 1000px) {{
            .grid {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .details {{
                grid-template-columns: 1fr 1fr;
            }}
        }}

        @media (max-width: 650px) {{
            .grid,
            .details {{
                grid-template-columns: 1fr;
            }}

            main {{
                padding: 12px;
            }}
        }}
    </style>
</head>

<body>

<header>
    <h1>Moil Bot</h1>
    <p>AI-powered multi-asset trading analysis dashboard</p>
</header>

<main>

    <div class="toolbar">
        <label for="instrument"><strong>Instrument:</strong></label>

        <select id="instrument" onchange="changeInstrument(this.value)">
            <option value="GBPUSD" {"selected" if symbol == "GBPUSD" else ""}>
                GBPUSD
            </option>
            <option value="EURUSD" {"selected" if symbol == "EURUSD" else ""}>
                EURUSD
            </option>
            <option value="USDJPY" {"selected" if symbol == "USDJPY" else ""}>
                USDJPY
            </option>
            <option value="US30" {"selected" if symbol == "US30" else ""}>
                US30
            </option>
            <option value="NAS100" {"selected" if symbol == "NAS100" else ""}>
                NAS100
            </option>
            <option value="GER40" {"selected" if symbol == "GER40" else ""}>
                GER40
            </option>
            <option value="XAUUSD" {"selected" if symbol == "XAUUSD" else ""}>
                XAUUSD
            </option>
            <option value="BTCUSD" {"selected" if symbol == "BTCUSD" else ""}>
                BTCUSD
            </option>
            <option value="ETHUSD" {"selected" if symbol == "ETHUSD" else ""}>
                ETHUSD
            </option>
            <option value="AAPL" {"selected" if symbol == "AAPL" else ""}>
                AAPL
            </option>
            <option value="NVDA" {"selected" if symbol == "NVDA" else ""}>
                NVDA
            </option>
        </select>
    </div>

    <div class="grid">

        <div class="card">
            <h3>Instrument</h3>
            <div class="value">{symbol}</div>
        </div>

        <div class="card">
            <h3>Asset Class</h3>
            <div class="value">Multi-Asset</div>
        </div>

        <div class="card">
            <h3>Structure</h3>
            <div class="value">Bullish</div>
        </div>

        <div class="card">
            <h3>Fundamental Bias</h3>
            <div class="value">Neutral</div>
        </div>

    </div>

    <div class="section">
        <h2>Market Overview</h2>

        <div class="details">

            <div class="detail">
                <strong>Price</strong>
                112.00
            </div>

            <div class="detail">
                <strong>Top-Down Alignment</strong>
                Bullish
            </div>

            <div class="detail">
                <strong>Setup Status</strong>
                Qualified
            </div>

            <div class="detail">
                <strong>Setup Score</strong>
                4 / 5
            </div>

            <div class="detail">
                <strong>Risk / Reward</strong>
                2.00
            </div>

            <div class="detail">
                <strong>Daily Risk</strong>
                1.00%
            </div>

        </div>
    </div>

    <div class="section">
        <h2>Price & Volume</h2>

        <div class="chart">
            {chart_html}
        </div>
    </div>

    <div class="section">
        <h2>Risk Overview</h2>

        <div class="details">

            <div class="detail">
                <strong>Account Balance</strong>
                R10,000.00
            </div>

            <div class="detail">
                <strong>Risk Per Trade</strong>
                1.00%
            </div>

            <div class="detail">
                <strong>Risk Amount</strong>
                R100.00
            </div>

            <div class="detail">
                <strong>Open Trades</strong>
                1
            </div>

            <div class="detail">
                <strong>Total Exposure</strong>
                1.00%
            </div>

            <div class="detail">
                <strong>Daily Loss</strong>
                0.00%
            </div>

        </div>
    </div>

    <div class="section">
        <h2>Backtest Overview</h2>

        <div class="details">

            <div class="detail">
                <strong>Total Trades</strong>
                10
            </div>

            <div class="detail">
                <strong>Winning Trades</strong>
                6
            </div>

            <div class="detail">
                <strong>Losing Trades</strong>
                4
            </div>

            <div class="detail">
                <strong>Win Rate</strong>
                60.00%
            </div>

            <div class="detail">
                <strong>Total Profit</strong>
                R600.00
            </div>

            <div class="detail">
                <strong>Profit Factor</strong>
                1.50
            </div>

        </div>
    </div>

</main>

<script>
function changeInstrument(symbol) {{
    window.location.href = "/?symbol=" + encodeURIComponent(symbol);
}}
</script>

</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):

    def do_GET(self) -> None:
        if self.path.startswith("/?symbol="):
            symbol = self.path.split("=", 1)[1]
            symbol = symbol.split("&", 1)[0]

            from urllib.parse import unquote

            symbol = unquote(symbol)

            html = build_dashboard_html(symbol)

        else:
            html = build_dashboard_html()

        encoded = html.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


def run_server() -> None:
    server = HTTPServer((HOST, PORT), DashboardHandler)

    print()
    print("==========================================")
    print(" Moil Bot Dashboard")
    print("==========================================")
    print(f" Dashboard: http://{HOST}:{PORT}")
    print(" Press Ctrl+C to stop the dashboard.")
    print("==========================================")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
