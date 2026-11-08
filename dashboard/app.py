from __future__ import annotations

import html
import ipaddress
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from alerts.engine import AlertEngine
from dashboard.mt5_live import MT5LiveService
from dashboard.realtime_pipeline import RealtimeTradingPipeline
from fundamentals.calendar_monitor import EconomicCalendarMonitor
from knowledge.unified_search import search_all_knowledge
from risk.account import calculate_account_risk
from execution.demo_start import DemoStartController
from execution.mt5_executor import MT5ExecutionService
from strategy.rule_registry import StrategyRuleRegistry
from chat.execution_bridge import post_demo_start_result
from chat.service import chat_service

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8501"))
CLOUD_MODE = os.environ.get("MOILBOT_CLOUD_MODE", "").lower() in {"1", "true", "yes"}

mt5_service = MT5LiveService()
alert_engine = AlertEngine()
calendar_monitor = EconomicCalendarMonitor(alert_engine=alert_engine)

SESSION: dict[str, Any] = {
    "connected": False,
    "account": None,
    "mode": None,
    "operating": False,
    "chat": [],
    "last_demo_start": None,
}


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def money(value: Any, currency: str = "") -> str:
    try:
        return f"{currency} {float(value):,.2f}".strip()
    except (TypeError, ValueError):
        return f"{currency} 0.00".strip()


def parse_form(body: bytes) -> dict[str, str]:
    data = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"))
    return {key: values[0] if values else "" for key, values in data.items()}


def nav_layout(title: str, content: str, active: str = "Overview") -> str:
    items = [
        ("Overview", "/"),
        ("Markets", "/markets"),
        ("Analysis", "/analysis"),
        ("Knowledge", "/knowledge"),
        ("Strategy", "/strategy"),
        ("Risk", "/risk"),
    ]
    nav = "".join(
        f'<a class="{"active" if name == active else ""}" href="{url}">{esc(name)}</a>'
        for name, url in items
    )
    status = (
        '<span class="status online">MT5 Connected</span>'
        if SESSION.get("connected") and SESSION.get("account")
        else '<span class="status offline">MT5 Offline</span>'
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Moil Bot — {esc(title)}</title>
<style>
body{{margin:0;font-family:Arial,sans-serif;background:#07121c;color:#edf7ff}}
.shell{{display:flex;min-height:100vh}}
.sidebar{{width:220px;background:#0a1722;padding:16px;border-right:1px solid #234}}
.nav a{{display:block;color:#dfefff;padding:10px;margin:4px 0;border-radius:8px;text-decoration:none}}
.nav a.active{{background:#1b3b55}}
.main{{flex:1;padding:20px}}
.card{{background:#102033;border:1px solid #2a4a66;border-radius:12px;padding:16px;margin-bottom:16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
.metric{{font-size:24px;font-weight:700}}
.muted{{color:#9fb6cc}}
.status{{padding:6px 10px;border-radius:999px;font-size:12px}}
.status.online{{background:#143;color:#79f0b3}}
.status.offline{{background:#411;color:#ff8c8c}}
input,select,button{{font:inherit;width:100%;padding:10px;margin:8px 0;border-radius:8px;border:1px solid #345;background:#0b1824;color:#eef6ff}}
button{{background:#1d6fd8;border:none;cursor:pointer}}
table{{width:100%;border-collapse:collapse}}
th,td{{border-bottom:1px solid #243b53;padding:8px;text-align:left}}
.danger{{color:#ff8c8c}}
</style></head>
<body><div class="shell"><aside class="sidebar"><h1>MOIL BOT</h1><nav class="nav">{nav}</nav><div>{status}</div></aside>
<main class="main"><h2>{esc(title)}</h2>{content}</main></div></body></html>"""


def connection_form(message: str = "") -> str:
    msg = f'<div class="card"><strong>Connection:</strong> {esc(message)}</div>' if message else ""
    return msg + """
    <div class="card">
      <h3>Connect MT5 Account</h3>
      <form method="POST" action="/connect">
        <label>Account Mode</label>
        <select name="mode"><option value="DEMO">DEMO</option><option value="REAL">REAL</option></select>
        <p class="muted">Use the account already signed in to your open MT5 terminal, or enter credentials to switch accounts.</p>
        <label>MT5 Login (optional)</label><input type="number" name="login" placeholder="Leave blank to use the signed-in terminal"/>
        <label>MT5 Server (optional)</label><input type="text" name="server" placeholder="Required only when entering login credentials"/>
        <label>Password (optional)</label><input type="password" name="password" placeholder="Required only when entering login credentials"/>
        <button type="submit">CONNECT MT5</button>
      </form>
    </div>"""


def get_account() -> Any:
    return SESSION.get("account")


def overview_page() -> str:
    account = get_account()
    if not SESSION.get("connected") or not account:
        return nav_layout("Overview", connection_form(), "Overview")
    risk = calculate_account_risk(balance=float(account.balance), risk_percent=1.0)
    content = f"""
    <div class="grid">
      <div class="card"><div class="muted">BALANCE</div><div class="metric">{money(account.balance, account.currency)}</div></div>
      <div class="card"><div class="muted">EQUITY</div><div class="metric">{money(account.equity, account.currency)}</div></div>
      <div class="card"><div class="muted">RISK 1%</div><div class="metric">{money(risk.risk_amount, account.currency)}</div></div>
    </div>
    <div class="card"><p class="muted">Account {esc(account.login)} on {esc(account.server)} ({esc(SESSION.get('mode'))})</p>
    <p><a href="/strategy">Open Strategy / Demo Start</a></p></div>"""
    return nav_layout("Overview", content, "Overview")


def markets_page() -> str:
    if not SESSION.get("connected"):
        return nav_layout("Markets", connection_form("Connect MT5 first."), "Markets")
    symbols = mt5_service.symbols()
    rows = "".join(
        f"<tr><td>{esc(i['symbol'])}</td><td>{i['bid']}</td><td>{i['ask']}</td>"
        f"<td><a href='/analysis?symbol={urllib.parse.quote(i['symbol'])}'>Analyse</a></td></tr>"
        for i in symbols[:25]
    ) or '<tr><td colspan="4">No symbols</td></tr>'
    return nav_layout("Markets", f'<div class="card"><table><thead><tr><th>Symbol</th><th>Bid</th><th>Ask</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>', "Markets")


def analysis_page(query: dict[str, list[str]]) -> str:
    symbol = (query.get("symbol", ["EURUSD"])[0] or "EURUSD").upper()
    if not SESSION.get("connected"):
        return nav_layout("Analysis", connection_form("Connect MT5 first."), "Analysis")
    pipeline = RealtimeTradingPipeline()
    decision = pipeline.evaluate(symbol, float(get_account().balance), risk_percent=1.0)
    content = f"""
    <div class="card">
      <h3>{esc(decision.symbol)} analysis</h3>
      <p>Status: {esc(decision.status)} · Direction: {esc(decision.direction)} · Score: {esc(decision.score)}</p>
      <p class="muted">{esc(' | '.join(decision.reasons[:5]))}</p>
      <p>Entry {esc(decision.entry)} · SL {esc(decision.stop_loss)} · TP {esc(decision.take_profit)}</p>
    </div>"""
    return nav_layout("Analysis", content, "Analysis")


def knowledge_page(query: dict[str, list[str]] | None = None) -> str:
    q = ""
    if query:
        q = (query.get("q", [""])[0] or "").strip()
    form = (
        '<div class="card"><form method="GET" action="/knowledge">'
        f'<input name="q" placeholder="Search PDF/video knowledge" value="{esc(q)}"/>'
        '<button type="submit">Search</button></form></div>'
    )
    results_html = ""
    if q:
        try:
            results = search_all_knowledge(q, limit=8)
            results_html = "".join(
                f"<div class='card'><strong>{esc(r.get('title'))}</strong>"
                f"<div class='muted'>{esc(r.get('source_type'))} {esc(r.get('page') or r.get('video_id') or '')}</div>"
                f"<p>{esc(r.get('snippet'))}</p></div>"
                for r in results
            ) or "<div class='card'><p class='muted'>No matches</p></div>"
        except Exception as exc:
            results_html = f"<div class='card'><p class='danger'>{esc(exc)}</p></div>"
    return nav_layout("Knowledge", form + results_html, "Knowledge")


def strategy_page(notice: str = "") -> str:
    if not SESSION.get("connected"):
        return nav_layout("Strategy", connection_form("Connect MT5 first."), "Strategy")
    account = get_account()
    decision = RealtimeTradingPipeline().evaluate("EURUSD", float(account.balance), risk_percent=1.0)
    try:
        rules = DemoStartController().reviewed_rules()
        rules_error = ""
    except Exception as exc:
        rules = []
        rules_error = str(exc)
    rows = "".join(
        f"<tr><td>{esc(r.get('rule_id'))}</td><td>{esc(r.get('name'))}</td>"
        f"<td>{esc(r.get('direction'))}</td><td>{esc(r.get('status'))}</td>"
        f"<td>{'yes' if r.get('demo_execution_enabled') else 'no'}</td></tr>"
        for r in rules
    ) or '<tr><td colspan="5">No reviewed rules found</td></tr>'
    last = SESSION.get("last_demo_start")
    last_html = (
        f"<div class='card'><h3>Last Demo Start</h3>"
        f"<p>{esc(last.get('status'))} · {esc(last.get('direction'))} · {esc(last.get('rule_name') or last.get('rule_id'))}</p>"
        f"<p class='muted'>{esc(last.get('reason'))}</p></div>"
        if last else "<div class='card'><p class='muted'>No demo start in this session yet.</p></div>"
    )
    notice_html = f"<div class='card'><strong>Notice:</strong> {esc(notice)}</div>" if notice else ""
    err_html = f"<div class='card'><p class='danger'>{esc(rules_error)}</p></div>" if rules_error else ""
    content = f"""
    {notice_html}{err_html}
    <div class="card">
      <h3>Strategy Decision</h3>
      <p>{esc(decision.symbol)} · {esc(decision.status)} · {esc(decision.direction)} · score {esc(decision.score)}</p>
      <p class="muted">{esc(' | '.join(decision.reasons[:4]))}</p>
      <p>Entry {esc(decision.entry)} · SL {esc(decision.stop_loss)} · TP {esc(decision.take_profit)}</p>
    </div>
    <div class="card">
      <h3>Human-reviewed rules</h3>
      <table><thead><tr><th>ID</th><th>Name</th><th>Direction</th><th>Status</th><th>Demo Exec</th></tr></thead>
      <tbody>{rows}</tbody></table>
    </div>
    <div class="card">
      <h3>Demo Start — strategy dry run</h3>
      <p class="muted">Evaluates reviewed strategy rules without sending an order.</p>
      <form method="POST" action="/demo_start">
        <label>Symbol</label><input type="text" name="symbol" value="EURUSD" required/>
        <button type="submit">ANALYSE DEMO SETUP</button>
      </form>
    </div>
    <div class="card">
      <h3>Approve a rule for DEMO forward-testing</h3>
      <p class="muted">This approval is only for a verified DEMO account. It does not enable real-money execution. Review the rule and its sources before approving.</p>
      <form method="POST" action="/enable_demo_rule">
        <label>Reviewed rule</label>
        <select name="rule_id" required>
          {''.join(f'<option value="{esc(r.get("rule_id"))}">{esc(r.get("name"))} ({esc(r.get("rule_id"))})</option>' for r in rules)}
        </select>
        <label>Type ENABLE DEMO EXECUTION</label>
        <input name="confirmation_phrase" type="text" required autocomplete="off"/>
        <button type="submit" {'disabled' if SESSION.get('mode') != 'DEMO' or not rules else ''}>APPROVE DEMO FORWARD-TESTING</button>
      </form>
    </div>
    <div class="card">
      <h3>Place a DEMO market order</h3>
      <p class="muted">Requires a verified DEMO account, an approved demo rule, a fresh verified economic calendar, valid setup confirmation, broker-based position sizing, stop loss and take profit, and your explicit confirmation. Maximum planned risk: 0.5%.</p>
      <form method="POST" action="/demo_start">
        <label>Symbol</label><input type="text" name="symbol" value="EURUSD" required/>
        <input type="hidden" name="execute_demo" value="yes"/>
        <label><input type="checkbox" name="confirm_demo_order" value="yes" required style="width:auto"/> I confirm that this may send a market order on my MT5 DEMO account.</label>
        <button type="submit" {'disabled' if SESSION.get('mode') != 'DEMO' else ''}>SEND DEMO MARKET ORDER</button>
      </form>
    </div>
    {last_html}
    """
    return nav_layout("Strategy", content, "Strategy")


def risk_page() -> str:
    if not SESSION.get("connected"):
        return nav_layout("Risk", connection_form("Connect MT5 first."), "Risk")
    account = get_account()
    risk = calculate_account_risk(balance=float(account.balance), risk_percent=1.0)
    content = f"""
    <div class="grid">
      <div class="card"><div class="muted">BALANCE</div><div class="metric">{money(account.balance, account.currency)}</div></div>
      <div class="card"><div class="muted">RISK AMOUNT</div><div class="metric">{money(risk.risk_amount, account.currency)}</div></div>
    </div>
    <div class="card"><ul>
      <li>Demo risk per trade: 0.5% by default; hard cap 1%</li>
      <li>Maximum one new trade per local day</li>
      <li>Maximum one open position</li>
      <li>Daily loss stop: 1%</li>
      <li>No new entries on a high-impact event date</li>
      <li>Real-money order execution remains disabled</li>
    </ul></div>"""
    return nav_layout("Risk", content, "Risk")


class MoilBotHandler(BaseHTTPRequestHandler):
    def is_local_dashboard_request(self) -> bool:
        try:
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                return False
            origin = urllib.parse.urlparse(self.headers.get("Origin", ""))
            host = urllib.parse.urlparse("//" + self.headers.get("Host", ""))
            allowed_hosts = {"127.0.0.1", "localhost", "::1"}
            return (
                origin.scheme == "http"
                and origin.hostname in allowed_hosts
                and origin.port == PORT
                and host.hostname in allowed_hosts
                and host.port == PORT
            )
        except (ValueError, TypeError):
            return False

    def send_html(self, page: str, status: int = 200) -> None:
        data = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str) -> None:
        self.send_response(302)
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
            page = knowledge_page(query)
        elif path == "/strategy":
            page = strategy_page(query.get("notice", [""])[0])
        elif path == "/risk":
            page = risk_page()
        elif path == "/disconnect":
            SESSION.update({"connected": False, "account": None, "mode": None, "operating": False})
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
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_form(self.rfile.read(length))

        if path == "/enable_demo_rule":
            if not self.is_local_dashboard_request():
                self.redirect("/strategy?notice=" + urllib.parse.quote("Demo rule approval requires a same-origin local dashboard request."))
                return
            if not SESSION.get("connected") or SESSION.get("mode") != "DEMO":
                self.redirect("/strategy?notice=" + urllib.parse.quote("Rule approval is available only on a verified DEMO account."))
                return
            try:
                registry = StrategyRuleRegistry()
                registry.enable_demo_execution(
                    rule_id=(form.get("rule_id") or "").strip(),
                    confirmation_phrase=(form.get("confirmation_phrase") or "").strip(),
                )
                notice = "Rule approved for DEMO forward-testing only. Real-money execution remains disabled."
            except Exception as exc:
                notice = f"Demo rule approval failed: {exc}"
            self.redirect("/strategy?notice=" + urllib.parse.quote(notice))
            return

        if path == "/demo_start":
            symbol = (form.get("symbol") or "EURUSD").strip().upper()
            execute_demo = form.get("execute_demo") == "yes"
            if not SESSION.get("connected"):
                self.redirect("/strategy?notice=" + urllib.parse.quote("Connect MT5 before Demo Start."))
                return
            account = get_account()
            actual_mode = str(getattr(account, "account_type", "") or SESSION.get("mode") or "UNKNOWN").upper()
            if execute_demo and (
                not self.is_local_dashboard_request()
                or actual_mode != "DEMO"
                or str(SESSION.get("mode") or "").upper() != "DEMO"
                or form.get("confirm_demo_order") != "yes"
            ):
                self.redirect("/strategy?notice=" + urllib.parse.quote("Order blocked: verified DEMO account and explicit order confirmation are required."))
                return
            try:
                calendar_verified = calendar_monitor.is_verified()
                high_impact_news = (
                    calendar_monitor.has_active_high_impact(symbol)
                    or calendar_monitor.has_high_impact_today(symbol)
                )
                if execute_demo and not calendar_verified:
                    raise RuntimeError("Economic calendar is not verified or is stale; demo execution is blocked.")
                if execute_demo and high_impact_news:
                    raise RuntimeError("High-impact economic event blackout is active for this symbol.")
                today_entries = mt5_service.today_entry_count() if execute_demo else 0
                if execute_demo and today_entries >= 1:
                    raise RuntimeError("One-trade-per-day limit reached. No additional order will be sent today.")
                if execute_demo and mt5_service.open_trade_count() >= 1:
                    raise RuntimeError("An MT5 position is already open. Close/manage it before another entry.")
                pipeline = RealtimeTradingPipeline()
                actual_symbol, datasets = pipeline._build_datasets(symbol)
                frame = datasets.get("M15")
                if frame is None or getattr(frame, "empty", True):
                    raise ValueError(f"No M15 data available for {symbol}.")
                if "timestamp" not in frame.columns and "time" in frame.columns:
                    frame = frame.copy()
                    frame["timestamp"] = frame["time"]
                executor = None
                if execute_demo:
                    executor = MT5ExecutionService(mt5_module=mt5_service.mt5)
                    executor.adopt_existing_connection()
                result = DemoStartController().start(
                    symbol=actual_symbol,
                    dataframe=frame,
                    account_mode=actual_mode,
                    allow_execution=execute_demo,
                    proposed_risk_percent=0.5,
                    daily_loss_percent=mt5_service.today_loss_percent() if execute_demo else 0.0,
                    open_trades=mt5_service.open_trade_count(),
                    daily_trade_count=today_entries,
                    fundamental_bias="neutral",
                    high_impact_news=high_impact_news,
                    calendar_verified=calendar_verified,
                    explicit_confirmation=(
                        execute_demo and form.get("confirm_demo_order") == "yes"
                    ),
                    executor=executor,
                    account_balance=float(account.balance),
                )
                SESSION["last_demo_start"] = {
                    "status": result.status,
                    "direction": result.direction,
                    "reason": result.reason,
                    "rule_id": result.rule_id,
                    "rule_name": result.rule_name,
                    "dry_run": result.dry_run,
                    "symbol": result.symbol,
                    "order_ticket": result.order_ticket,
                }
                try:
                    post_demo_start_result(result)
                except Exception:
                    pass
                notice = result.reason
            except Exception as exc:
                notice = f"Demo Start failed: {exc}"
            self.redirect("/strategy?notice=" + urllib.parse.quote(notice))
            return

        if path != "/connect":
            self.send_html("<h1>404</h1>", 404)
            return
        if CLOUD_MODE:
            self.send_html("<h1>MT5 connections are disabled on the hosted cloud version.</h1>", 503)
            return
        try:
            mode = (form.get("mode") or "DEMO").upper()
            raw_login = (form.get("login") or "").strip()
            password = form.get("password") or ""
            server = (form.get("server") or "").strip()
            if raw_login and (not password or not server):
                raise ValueError("Enter the MT5 password and server with the login, or leave all three blank to use the signed-in terminal.")
            result = mt5_service.connect(
                login=int(raw_login) if raw_login else None,
                password=password,
                server=server,
                requested_mode=mode,
            )
            if result.connected:
                SESSION["connected"] = True
                SESSION["account"] = result
                SESSION["mode"] = result.account_type
                self.redirect("/")
                return
            self.send_html(nav_layout("Connection", connection_form(result.message), "Overview"), 401)
        except Exception as exc:
            self.send_html(nav_layout("Connection", connection_form(str(exc)), "Overview"), 500)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[MOIL BOT] {format % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MoilBotHandler)
    calendar_monitor.start()
    print(f"Dashboard running at http://{HOST}:{PORT}")
    print("Demo Start: reviewed-rule DEMO market orders available after explicit confirmation; REAL accounts blocked")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        calendar_monitor.stop()
        mt5_service.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
