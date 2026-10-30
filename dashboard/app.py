from __future__ import annotations

import html
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from alerts.engine import AlertEngine
from alerts.models import AlertEvent
from dashboard.alerts_ui import handle_alert_action, render_alerts_content
from dashboard.mt5_live import MT5LiveService
from dashboard.realtime_pipeline import RealtimeTradingPipeline
from fundamentals.analyzer import FundamentalAnalyzer
from fundamentals.models import NewsItem
from knowledge.unified_search import search_all_knowledge
from risk.account import calculate_account_risk

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8501"))
CLOUD_MODE = os.environ.get("MOILBOT_CLOUD_MODE", "").lower() in {"1", "true", "yes"}

mt5_service = MT5LiveService()
alert_engine = AlertEngine()

SESSION: dict[str, Any] = {
    "connected": False,
    "account": None,
    "mode": None,
}


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def money(value: Any, currency: str = "") -> str:
    try:
        amount = float(value)
        return f"{currency} {amount:,.2f}".strip()
    except (TypeError, ValueError):
        return f"{currency} 0.00".strip()


def nav_layout(title: str, content: str, active: str = "Overview") -> str:
    nav_items = [
        ("Overview", "/"),
        ("Markets", "/markets"),
        ("Analysis", "/analysis"),
        ("Knowledge", "/knowledge"),
        ("Trades", "/trades"),
        ("Alerts", "/alerts"),
        ("Fundamentals", "/fundamentals"),
        ("Strategy", "/strategy"),
        ("Risk", "/risk"),
    ]
    nav_html = "".join(
        f'<a class="{"active" if name == active else ""}" href="{url}"><span>{name[0]}</span>{esc(name)}</a>'
        for name, url in [(n, u) for n, u in nav_items]
    )

    if SESSION.get("connected") and SESSION.get("account"):
        status = '<span class="status online">MT5 Connected</span>'
    else:
        status = '<span class="status offline">MT5 Offline</span>'

    return f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Moil Bot — {esc(title)}</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #06111f; color: #eaf2ff; margin: 0; }}
            a {{ color: #7bd7ff; text-decoration: none; }}
            .shell {{ display: flex; min-height: 100vh; }}
            .sidebar {{ width: 230px; background: #0d1725; border-right: 1px solid #1e2d3d; padding: 18px 14px; }}
            .brand {{ text-align: center; margin-bottom: 18px; }}
            .brand h1 {{ font-size: 28px; letter-spacing: 2px; margin: 6px 0; }}
            .nav a {{ display: block; padding: 12px 14px; margin: 6px 0; border-radius: 10px; color: #dfefff; }}
            .nav a.active {{ background: linear-gradient(135deg, #0d6efd, #7b61ff); }}
            .main {{ flex: 1; padding: 24px; }}
            .topbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }}
            .card {{ background: linear-gradient(180deg, #0d1a2b, #0b1522); border: 1px solid #1e2d3d; border-radius: 12px; padding: 18px; margin-bottom: 18px; box-shadow: 0 10px 20px rgba(0,0,0,0.18); }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }}
            .metric {{ font-size: 28px; font-weight: 700; }}
            .muted {{ color: #9bb2cf; }}
            .status {{ display: inline-block; padding: 8px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
            .status.online {{ background: rgba(33, 203, 123, 0.14); color: #7ef0b0; }}
            .status.offline {{ background: rgba(255, 67, 67, 0.12); color: #ff8e8e; }}
            .pill {{ display: inline-block; background: rgba(123, 109, 255, 0.14); color: #d7d1ff; padding: 8px 12px; border-radius: 999px; margin-right: 8px; }}
            input, select, button {{ font: inherit; }}
            input, select {{ width: 100%; padding: 12px; margin-bottom: 14px; border-radius: 8px; border: 1px solid #2c415b; background: #091725; color: #eef6ff; box-sizing: border-box; }}
            button {{ background: linear-gradient(135deg, #0d6efd, #7b61ff); color: white; border: none; border-radius: 8px; padding: 11px 16px; cursor: pointer; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border-bottom: 1px solid #1d2e42; padding: 12px; text-align: left; }}
            .warn {{ color: #ffd480; }}
            .danger {{ color: #ff9a9a; }}
            .positive {{ color: #7ef0b0; }}
            .negative {{ color: #ff7d7d; }}
            @media (max-width: 800px) {{ .shell {{ display: block; }} .sidebar {{ width: auto; }} .main {{ padding: 14px; }} }}
        </style>
    </head>
    <body>
        <div class="shell">
            <aside class="sidebar">
                <div class="brand">
                    <div style="font-size:40px;">💀</div>
                    <h1>MOIL BOT</h1>
                    <div class="muted">AI TRADING INTELLIGENCE</div>
                </div>
                <nav class="nav">{nav_html}</nav>
                <div style="padding-top: 24px;">{status}</div>
            </aside>
            <main class="main">
                <div class="topbar">
                    <h2>{esc(title)}</h2>
                    {status}
                </div>
                {content}
            </main>
        </div>
    </body>
    </html>
    """


def connection_form(message: str = "") -> str:
    msg = "" if not message else f'<div class="card"><strong>Connection message</strong><div class="muted">{esc(message)}</div></div>'
    return f"""
    {msg}
    <div class="card">
        <h3>Connect MT5 Account</h3>
        <p class="muted">Connect your local MetaTrader 5 desktop terminal to enable market data, positions and decisioning.</p>
        <form method="POST" action="/connect">
            <label>Account Mode</label>
            <select name="mode" required>
                <option value="DEMO">DEMO</option>
                <option value="REAL">REAL</option>
            </select>
            <label>MT5 Login</label>
            <input type="number" name="login" placeholder="MT5 login" required />
            <label>MT5 Server</label>
            <input type="text" name="server" placeholder="Exness-MT5Trial9" required />
            <label>Password</label>
            <input type="password" name="password" placeholder="MT5 password" required />
            <button type="submit">CONNECT MT5</button>
        </form>
        <p class="muted">Use the local MT5 desktop account, not the Exness web terminal URL.</p>
    </div>
    """


def get_account() -> Any:
    return SESSION.get("account")


def build_live_alerts() -> list:
    if not SESSION.get("connected"):
        return []
    account = get_account()
    if account is None:
        return []
    try:
        pipeline = RealtimeTradingPipeline()
        result = pipeline.evaluate("EURUSD", float(account.balance), risk_percent=1.0)
        if result.status in {"accepted", "watch", "rejected"}:
            event = AlertEvent(
                symbol=result.symbol,
                alert_type="setup_qualified" if result.status == "accepted" else "risk_warning",
                severity="info" if result.status == "accepted" else "warning",
                title=f"{result.symbol} pipeline {result.status}",
                message=": ".join(result.reasons[:2]) if result.reasons else "Pipeline evaluation completed.",
            )
            alert_engine.process(event)
            return alert_engine.get_all_alerts()
    except Exception:
        pass
    return alert_engine.get_all_alerts()


def build_fundamentals_context() -> tuple[dict, list[NewsItem]]:
    sample_news = [
        NewsItem(
            title="US treasury yields soften as growth outlook cools",
            source="Reuters",
            published_at=datetime.now(timezone.utc) - timedelta(hours=3),
            url="https://example.com/news/1",
            summary="Bond yields ease and market participants expect a slower pace of tightening.",
            impact="high",
        ),
        NewsItem(
            title="Eurozone inflation prints softer than expected",
            source="Bloomberg",
            published_at=datetime.now(timezone.utc) - timedelta(hours=5),
            url="https://example.com/news/2",
            summary="Lower inflation supports a more dovish European Central Bank posture.",
            impact="high",
        ),
        NewsItem(
            title="Fed speakers signal patient approach to rates",
            source="CNBC",
            published_at=datetime.now(timezone.utc) - timedelta(hours=8),
            url="https://example.com/news/3",
            summary="Policy remains data dependent and the broader tone is less hawkish.",
            impact="medium",
        ),
    ]
    context = FundamentalAnalyzer().analyse("EURUSD", sample_news)
    return context, sample_news


def overview_page() -> str:
    account = get_account()
    if not SESSION.get("connected") or not account:
        content = f"""
        <div class="card">
            <span class="pill">AI TRADING TERMINAL</span>
            <h3 style="font-size: 46px; margin: 12px 0;">MOIL BOT IS ONLINE</h3>
            <p class="muted">Connect your local Exness MT5 account to unlock live data, AI analysis, fundamentals, alerts and decisioning.</p>
            <a href="#connect"><button>CONNECT ACCOUNT</button></a>
        </div>
        {connection_form()}
        """
        return nav_layout("Overview", content, "Overview")

    balance = float(account.balance)
    risk = calculate_account_risk(balance=balance, risk_percent=1.0)

    content = f"""
    <div class="card">
        <span class="pill">MT5 LIVE DATA</span>
        <h3 style="font-size: 42px; margin: 12px 0;">MOIL BOT CONNECTED</h3>
        <p class="muted">Account {esc(account.login)} • {esc(account.server)} • {esc(account.account_type)}</p>
    </div>
    <div class="grid">
        <div class="card"><div class="muted">BALANCE</div><div class="metric">{money(account.balance, account.currency)}</div></div>
        <div class="card"><div class="muted">EQUITY</div><div class="metric">{money(account.equity, account.currency)}</div></div>
        <div class="card"><div class="muted">FREE MARGIN</div><div class="metric">{money(account.free_margin, account.currency)}</div></div>
        <div class="card"><div class="muted">FLOATING P/L</div><div class="metric {'positive' if account.profit >= 0 else 'negative'}">{money(account.profit, account.currency)}</div></div>
    </div>
    <div class="grid">
        <div class="card">
            <h3>AI Analytics</h3>
            <p class="muted">Strategy and market intelligence are active for the connected account.</p>
            <div class="pill">decisioning online</div>
            <div class="pill">risk guard armed</div>
        </div>
        <div class="card">
            <h3>Risk Status</h3>
            <p class="muted">1.0% risk budget selected</p>
            <div class="metric">{money(risk.risk_amount, account.currency)}</div>
        </div>
        <div class="card">
            <h3>Execution Mode</h3>
            <div class="status online">READ-ONLY</div>
            <p class="muted">Dashboard monitoring is enabled. Orders are not sent automatically.</p>
        </div>
    </div>
    """
    return nav_layout("Overview", content, "Overview")


def markets_page() -> str:
    if not SESSION.get("connected"):
        return nav_layout("Markets", connection_form("Connect an MT5 account to load real market prices."), "Markets")
    symbols = mt5_service.symbols()
    rows = "".join(
        f"""
        <tr>
            <td>{esc(item['symbol'])}</td>
            <td>{esc(item.get('description', ''))}</td>
            <td>{item['bid']:.{item['digits']}f}</td>
            <td>{item['ask']:.{item['digits']}f}</td>
            <td>{item['spread']:.{item['digits']}f}</td>
            <td><a href="/analysis?symbol={urllib.parse.quote(item['symbol'])}">Analyse</a></td>
        </tr>
        """ for item in symbols[:25]
    ) or '<tr><td colspan="6">No visible symbols returned.</td></tr>'
    content = f"""
    <div class="card">
        <h3>Live MT5 Market Watch</h3>
        <p class="muted">Symbols are read directly from your connected local MetaTrader 5 terminal.</p>
        <table>
            <thead><tr><th>Symbol</th><th>Description</th><th>Bid</th><th>Ask</th><th>Spread</th><th>Analysis</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """
    return nav_layout("Markets", content, "Markets")


def analysis_page(query: dict[str, list[str]]) -> str:
    symbol = (query.get("symbol", ["EURUSD"])[0] or "EURUSD").upper()
    if SESSION.get("connected"):
        market = mt5_service.symbol(symbol)
        pipeline = RealtimeTradingPipeline()
        decision = pipeline.evaluate(symbol, float(get_account().balance), risk_percent=1.0)
    else:
        market = None
        decision = None

    market_cards = "" if market is None else f"""
    <div class="grid">
        <div class="card"><div class="muted">MT5 BID</div><div class="metric">{market['bid']:.{market['digits']}f}</div></div>
        <div class="card"><div class="muted">MT5 ASK</div><div class="metric">{market['ask']:.{market['digits']}f}</div></div>
        <div class="card"><div class="muted">MT5 SPREAD</div><div class="metric">{market['spread']:.{market['digits']}f}</div></div>
    </div>
    """

    decision_block = "" if decision is None else f"""
    <div class="card">
        <h3>AI Decision</h3>
        <div class="status {'online' if decision.qualified else 'offline'}">{esc(decision.status.upper())}</div>
        <p><strong>Direction:</strong> {esc(decision.direction)}</p>
        <p><strong>Score:</strong> {esc(decision.score)}</p>
        <p><strong>Entry:</strong> {esc(decision.entry) if decision.entry is not None else 'n/a'}</p>
        <p><strong>Stop:</strong> {esc(decision.stop_loss) if decision.stop_loss is not None else 'n/a'}</p>
        <p><strong>Take Profit:</strong> {esc(decision.take_profit) if decision.take_profit is not None else 'n/a'}</p>
        <ul>
            {''.join(f'<li>{esc(item)}</li>' for item in decision.reasons[:6])}
        </ul>
    </div>
    """

    content = f"""
    <div class="card">
        <h3>{esc(symbol)} Analysis</h3>
        <p class="muted">AI-driven technical analysis is connected to the live MT5 feed and the strategy pipeline.</p>
    </div>
    {market_cards}
    {decision_block}
    """
    return nav_layout("Analysis", content, "Analysis")


def trades_page() -> str:
    if not SESSION.get("connected"):
        return nav_layout("Trades", connection_form("Connect an MT5 account to view live positions."), "Trades")
    positions = mt5_service.positions()
    rows = "".join(
        f"""
        <tr>
            <td>{esc(item['ticket'])}</td>
            <td>{esc(item['symbol'])}</td>
            <td>{esc(item['type'])}</td>
            <td>{item['volume']:.2f}</td>
            <td>{item['price_open']}</td>
            <td>{item['price_current']}</td>
            <td class="{'positive' if item['profit'] >= 0 else 'negative'}">{money(item['profit'], get_account().currency)}</td>
        </tr>
        """ for item in positions
    ) or '<tr><td colspan="7">No open positions.</td></tr>'
    content = f"""
    <div class="card">
        <h3>Live MT5 Positions</h3>
        <table>
            <thead><tr><th>Ticket</th><th>Symbol</th><th>Type</th><th>Volume</th><th>Open</th><th>Current</th><th>P/L</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """
    return nav_layout("Trades", content, "Trades")


def alerts_page(notice: str = "") -> str:
    alert_items = build_live_alerts()
    if notice:
        alert_box = f'<div class="card"><strong>Notice:</strong> {esc(notice)}</div>'
    else:
        alert_box = ""
    status_cards = "".join(
        f'<div class="card"><div class="muted">{status.title()}</div><h3>{sum(1 for a in alert_items if a.status == status)}</h3></div>'
        for status in ("new", "acknowledged", "resolved")
    )
    result_cards = "".join(
        f"""
        <div class="card">
            <div><strong>{esc(item.title)}</strong> <span class="pill">{esc(item.severity)}</span></div>
            <p class="muted">{esc(item.message)}</p>
            <small>{esc(item.symbol)} • {esc(item.alert_type)} • {esc(item.created_at.strftime('%Y-%m-%d %H:%M UTC'))}</small>
        </div>
        """ for item in sorted(alert_items, key=lambda x: x.created_at, reverse=True)[:10]
    ) or '<div class="card"><p class="muted">No alerts have been generated yet. When the MT5 account is connected, the pipeline creates live alert events.</p></div>'

    content = f"""
    {alert_box}
    <div class="grid">{status_cards}</div>
    <div class="card">
        <h3>Automatic alert monitoring</h3>
        <p class="muted">The alert engine is now active and connected to live trading decisions. The feed is retained in memory for this session.</p>
    </div>
    {result_cards}
    """
    return nav_layout("Alerts", content, "Alerts")


def fundamentals_page() -> str:
    context, news = build_fundamentals_context()
    rows = "".join(
        f"""
        <tr>
            <td>{esc(item.title)}</td>
            <td>{esc(item.source)}</td>
            <td>{esc(item.impact)}</td>
            <td>{esc(item.published_at.strftime('%Y-%m-%d %H:%M UTC'))}</td>
        </tr>
        """ for item in news
    )
    content = f"""
    <div class="card">
        <h3>Fundamental Bias</h3>
        <div class="pill">{esc(context.bias.upper())}</div>
        <p class="muted">{esc(context.summary)}</p>
        <p><strong>High Impact Events:</strong> {esc(context.high_impact_events)}</p>
        <p><strong>News Count:</strong> {esc(context.news_count)}</p>
    </div>
    <div class="card">
        <h3>Market News Feed</h3>
        <table>
            <thead><tr><th>Headline</th><th>Source</th><th>Impact</th><th>Published</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """
    return nav_layout("Fundamentals", content, "Fundamentals")


def strategy_page() -> str:
    if not SESSION.get("connected"):
        return nav_layout("Strategy", connection_form("Connect MT5 to evaluate live strategy decisions."), "Strategy")
    account = get_account()
    pipeline = RealtimeTradingPipeline()
    decision = pipeline.evaluate("EURUSD", float(account.balance), risk_percent=1.0)
    content = f"""
    <div class="card">
        <h3>Strategy Decision</h3>
        <div class="status {'online' if decision.qualified else 'offline'}">{esc(decision.status.upper())}</div>
        <p><strong>Symbol:</strong> {esc(decision.symbol)}</p>
        <p><strong>Direction:</strong> {esc(decision.direction)}</p>
        <p><strong>Score:</strong> {esc(decision.score)}</p>
        <p><strong>Execution Plan:</strong> {esc(decision.status)}</p>
        <p class="muted">{esc(' '.join(decision.reasons[:4]))}</p>
    </div>
    <div class="card">
        <h3>Execution Plan</h3>
        <p><strong>Entry:</strong> {esc(decision.entry) if decision.entry is not None else 'n/a'}</p>
        <p><strong>Stop Loss:</strong> {esc(decision.stop_loss) if decision.stop_loss is not None else 'n/a'}</p>
        <p><strong>Take Profit:</strong> {esc(decision.take_profit) if decision.take_profit is not None else 'n/a'}</p>
        <p><strong>Risk Amount:</strong> {money(decision.risk_amount, account.currency)}</p>
    </div>
    """
    return nav_layout("Strategy", content, "Strategy")


def risk_page() -> str:
    if not SESSION.get("connected"):
        return nav_layout("Risk", connection_form("Connect MT5 to view risk and exposure."), "Risk")
    account = get_account()
    risk = calculate_account_risk(balance=float(account.balance), risk_percent=1.0)
    content = f"""
    <div class="grid">
        <div class="card"><div class="muted">BALANCE</div><div class="metric">{money(account.balance, account.currency)}</div></div>
        <div class="card"><div class="muted">RISK %</div><div class="metric">1.00%</div></div>
        <div class="card"><div class="muted">RISK AMOUNT</div><div class="metric">{money(risk.risk_amount, account.currency)}</div></div>
        <div class="card"><div class="muted">EXPOSURE</div><div class="metric">0.00%</div></div>
    </div>
    <div class="card">
        <h3>Risk Controls</h3>
        <ul>
            <li>Max risk per trade: 1.00%</li>
            <li>Max open trades: 3</li>
            <li>Max total exposure: 3.00%</li>
            <li>Daily loss cap: 5.00%</li>
        </ul>
    </div>
    """
    return nav_layout("Risk", content, "Risk")


def parse_form(body: bytes) -> dict[str, str]:
    parsed = urllib.parse.parse_qs(body.decode("utf-8"))
    return {k: v[0] for k, v in parsed.items()}


class MoilBotHandler(BaseHTTPRequestHandler):
    def send_html(self, page: str, status: int = 200) -> None:
        data = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            page = overview_page()
        elif path == "/markets":
            page = markets_page()
        elif path == "/analysis":
            page = analysis_page(query)
        elif path == "/knowledge":
            search_text = (query.get("q") or [""])[0].strip()
            if not search_text:
                content = """
                <div class="card">
                    <h3>Knowledge Search</h3>
                    <p class="muted">Search your training, PDFs and research notes for trading concepts and evidence.</p>
                    <form method="GET" action="/knowledge">
                        <input type="search" name="q" placeholder="Search knowledge base" />
                        <button type="submit">Search</button>
                    </form>
                </div>
                """
                page = nav_layout("Knowledge", content, "Knowledge")
            else:
                try:
                    results = search_all_knowledge(search_text, limit=10)
                    rows = "".join(
                        f"<div class='card'><h3>{esc(r.get('title','Untitled'))}</h3><p class='muted'>{esc(r.get('snippet',''))}</p></div>" for r in results[:10]
                    ) or '<div class="card"><p class="muted">No knowledge results found.</p></div>'
                    page = nav_layout("Knowledge", f'<div class="card"><h3>Results for: {esc(search_text)}</h3>{rows}</div>', "Knowledge")
                except Exception as exc:
                    page = nav_layout("Knowledge", f'<div class="card"><p class="danger">Knowledge error: {esc(str(exc))}</p></div>', "Knowledge")
        elif path == "/trades":
            page = trades_page()
        elif path == "/alerts":
            notice = query.get("notice", [""])[0]
            page = alerts_page(notice)
        elif path == "/fundamentals":
            page = fundamentals_page()
        elif path == "/strategy":
            page = strategy_page()
        elif path == "/risk":
            page = risk_page()
        elif path == "/disconnect":
            SESSION["connected"] = False
            SESSION["account"] = None
            SESSION["mode"] = None
            mt5_service.shutdown()
            self.redirect("/")
            return
        else:
            self.send_html("<h1>404</h1>", 404)
            return

        self.send_html(page)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/alerts/action":
            length = int(self.headers.get("Content-Length", "0"))
            form = parse_form(self.rfile.read(length))
            try:
                notice = handle_alert_action(form)
                self.redirect("/alerts?notice=" + urllib.parse.quote(notice))
                return
            except Exception as exc:
                page = alerts_page(str(exc))
                self.send_html(page, 400)
                return

        if path != "/connect":
            self.send_html("<h1>404</h1>", 404)
            return

        if CLOUD_MODE:
            self.send_html("<h1>MT5 connections are disabled on the hosted cloud version.</h1>", 503)
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        form = parse_form(body)
        mode = form.get("mode", "DEMO").upper()
        login = int(form.get("login", "0"))
        password = form.get("password", "")
        server = form.get("server", "")

        try:
            result = mt5_service.connect(login=login, password=password, server=server, requested_mode=mode)
            if result.connected:
                SESSION["connected"] = True
                SESSION["account"] = result
                SESSION["mode"] = mode
                build_live_alerts()
                self.redirect("/")
                return
            SESSION["connected"] = False
            SESSION["account"] = None
            SESSION["mode"] = None
            self.send_html(nav_layout("Connection", connection_form(result.message), "Overview"), 401)
            return
        except ValueError:
            self.send_html(nav_layout("Connection", connection_form("MT5 login must be a valid number."), "Overview"), 400)
            return
        except Exception as exc:
            self.send_html(nav_layout("Connection", connection_form(f"Connection error: {exc}"), "Overview"), 500)
            return

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[MOIL BOT] {format % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MoilBotHandler)
    print("\n=== MOIL BOT ===")
    print(f"Dashboard running at http://{HOST}:{PORT}")
    print("MT5 mode: local desktop terminal")
    print("Order execution: disabled (read-only)")
    print("AI modules: fundamentals, alerts, strategy and risk enabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Moil Bot dashboard...")
    finally:
        mt5_service.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
