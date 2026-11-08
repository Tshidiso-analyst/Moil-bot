from __future__ import annotations

import html
import ipaddress
import os
import threading
import time
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
from auth.service import AuthService, AuthenticationError, RegistrationError
from auth.web import build_expired_session_cookie, build_session_cookie, get_session_token

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8501"))
CLOUD_MODE = os.environ.get("MOILBOT_CLOUD_MODE", "").lower() in {"1", "true", "yes"}
AUTH_REQUIRED = CLOUD_MODE or os.environ.get("MOILBOT_AUTH_REQUIRED", "").lower() in {"1", "true", "yes"}
COOKIE_SECURE = os.environ.get("MOILBOT_COOKIE_SECURE", "true" if AUTH_REQUIRED else "false").lower() in {"1", "true", "yes"}
ALLOW_REGISTRATION = os.environ.get("MOILBOT_ALLOW_REGISTRATION", "false").lower() in {"1", "true", "yes"}
auth_service = AuthService()
LOGIN_FAILURES: dict[str, list[float]] = {}
LOGIN_FAILURES_LOCK = threading.Lock()
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 900

mt5_service = MT5LiveService()
if CLOUD_MODE or os.environ.get("MOILBOT_ALERT_STORE", "").strip().lower() == "postgres":
    from alerts.postgres_store import PostgresAlertStore
    alert_engine = AlertEngine(store=PostgresAlertStore())
else:
    alert_engine = AlertEngine()
calendar_monitor = EconomicCalendarMonitor(alert_engine=alert_engine)

DEMO_START_LOCK = threading.Lock()

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


def parse_mt5_credentials(form: dict[str, str]) -> tuple[int | None, str, str]:
    """Return either no credentials or a complete, validated MT5 credential set."""
    raw_login = (form.get("login") or "").strip()
    password = form.get("password") or ""
    server = (form.get("server") or "").strip()
    if not any((raw_login, password, server)):
        return None, "", ""
    if not all((raw_login, password, server)):
        raise ValueError(
            "To switch MT5 accounts, provide the account number, trading password, "
            "and exact broker server together. Leave all three blank to reuse the "
            "account already signed in to the terminal."
        )
    try:
        login = int(raw_login)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("MT5 login must be a positive account number.") from exc
    if login <= 0:
        raise ValueError("MT5 login must be a positive account number.")
    if len(server) > 128 or any(ord(char) < 32 for char in server):
        raise ValueError("MT5 server name is invalid.")
    return login, password, server


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
    disconnect_control = (
        '<form method="POST" action="/disconnect"><button type="submit">DISCONNECT MT5</button></form>'
        if SESSION.get("connected") and not CLOUD_MODE else ""
    )
    auth_controls = (
        '<form method="POST" action="/logout"><button type="submit">SIGN OUT</button></form>'
        if AUTH_REQUIRED else ""
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
<body><div class="shell"><aside class="sidebar"><h1>MOIL BOT</h1><nav class="nav">{nav}</nav><div>{status}{disconnect_control}{auth_controls}</div></aside>
<main class="main"><h2>{esc(title)}</h2>{content}</main></div></body></html>"""


def connection_form(message: str = "") -> str:
    msg = f'<div class="card"><strong>Connection:</strong> {esc(message)}</div>' if message else ""
    return msg + """
    <div class="card">
      <h3>Connect MT5 Account</h3>
      <form method="POST" action="/connect">
        <label>Account Mode</label>
        <select name="mode"><option value="DEMO">DEMO</option><option value="REAL">REAL</option></select>
        <p class="muted">Connect to any broker that provides a MetaTrader 5 account. You can reuse the account already signed in to the local terminal, or enter credentials for another account.</p>
        <label>MT5 Account Login</label><input type="number" name="login" min="1" step="1" placeholder="Your broker's MT5 account number"/>
        <label>Broker MT5 Server</label><input type="text" name="server" maxlength="128" autocomplete="off" placeholder="Exact server name from your broker account details"/>
        <p class="muted">Exness accounts use different assigned servers (for example, Exness-MT5Trial8 or Exness-MT5Real10). Other brokers work too: enter the exact server name shown in that broker's MT5 account details. Do not guess the server.</p>
        <label>MT5 Trading Password</label><input type="password" name="password" autocomplete="off" placeholder="Trading password for this MT5 account"/>
        <label>MT5 Terminal EXE Path (optional)</label><input type="text" name="terminal_path" maxlength="512" autocomplete="off" placeholder="Leave blank to use the default MT5 terminal path"/>
        <p class="muted">If you installed a broker-branded MT5 terminal (such as Exness) in a different folder, enter its terminal64.exe path here. This lets Moil-bot connect to that broker's own terminal installation. Leave blank to use the configured default path.</p>
        <p class="muted">Leave all three credential fields blank only if you want to use the account already signed in to the open MT5 terminal. Credentials are sent to your local MT5 terminal and are not saved by this form.</p>
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
        <label>Verified macro bias (manual declaration)</label>
        <p class="muted">Moil-bot does not independently calculate DXY direction yet. Only select a directional bias after checking DXY and the relevant macro context yourself.</p>
        <select name="fundamental_bias">
          <option value="neutral">Neutral / not verified</option>
          <option value="bullish">Bullish for this symbol</option>
          <option value="bearish">Bearish for this symbol</option>
        </select>
        <label><input type="checkbox" name="confirm_macro_bias" value="yes" required style="width:auto"/> I reviewed DXY, relevant economic releases and broader macro context; this directional bias is verified.</label>
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



def auth_page(title: str, content: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>{esc(title)} · Moil-bot</title>
    <style>
      body{{font-family:Arial,sans-serif;background:#101827;color:#eef2f7;display:grid;place-items:center;min-height:100vh;margin:0}}
      main{{width:min(92vw,420px);background:#1b2638;padding:28px;border-radius:14px;box-sizing:border-box}}
      label{{display:block;margin:14px 0 6px}} input{{box-sizing:border-box;width:100%;padding:12px;border-radius:7px;border:1px solid #526078;background:#101827;color:white}}
      button{{margin-top:18px;width:100%;padding:12px;border:0;border-radius:7px;background:#4f8cff;color:white;font-weight:bold;cursor:pointer}}
      a{{color:#91b9ff}} .notice{{color:#ffd28a}} p{{line-height:1.5}}
    </style></head><body><main><h1>{esc(title)}</h1>{content}</main></body></html>"""


def login_page(notice: str = "") -> str:
    message = f'<p class="notice">{esc(notice)}</p>' if notice else ""
    content = message + """
      <form method="POST" action="/login">
        <label>Username or email</label><input name="identifier" autocomplete="username" required maxlength="191"/>
        <label>Password</label><input type="password" name="password" autocomplete="current-password" required/>
        <button type="submit">Sign in</button>
      </form>"""
    if ALLOW_REGISTRATION:
        content += '<p>New to Moil-bot? <a href="/register">Create an account</a></p>'
    return auth_page("Sign in to Moil-bot", content)


def register_page(notice: str = "") -> str:
    message = f'<p class="notice">{esc(notice)}</p>' if notice else ""
    content = message + """
      <form method="POST" action="/register">
        <label>Full name</label><input name="full_name" autocomplete="name" required maxlength="150"/>
        <label>Username</label><input name="username" autocomplete="username" required minlength="3" maxlength="50"/>
        <label>Email</label><input type="email" name="email" autocomplete="email" required maxlength="191"/>
        <label>Password (at least 8 characters)</label><input type="password" name="password" autocomplete="new-password" required minlength="8"/>
        <button type="submit">Create account</button>
      </form><p>Already registered? <a href="/login">Sign in</a></p>"""
    return auth_page("Create your Moil-bot account", content)


def login_rate_limited(client_ip: str) -> bool:
    """Atomically count login attempts to prevent concurrent throttle bypass."""
    now = time.monotonic()
    with LOGIN_FAILURES_LOCK:
        for known_ip, known_attempts in list(LOGIN_FAILURES.items()):
            fresh = [
                stamp for stamp in known_attempts
                if now - stamp < LOGIN_WINDOW_SECONDS
            ]
            if fresh:
                LOGIN_FAILURES[known_ip] = fresh
            else:
                LOGIN_FAILURES.pop(known_ip, None)
        attempts = LOGIN_FAILURES.get(client_ip, [])
        if len(attempts) >= LOGIN_MAX_ATTEMPTS:
            LOGIN_FAILURES[client_ip] = attempts
            return True
        attempts.append(now)
        LOGIN_FAILURES[client_ip] = attempts
        return False


def clear_login_failures(client_ip: str) -> None:
    with LOGIN_FAILURES_LOCK:
        LOGIN_FAILURES.pop(client_ip, None)


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

    def send_html(self, page: str, status: int = 200, cookie: str | None = None) -> None:
        data = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str, cookie: str | None = None) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def same_origin_post(self) -> bool:
        origin = urllib.parse.urlparse(self.headers.get("Origin", ""))
        host = (self.headers.get("Host") or "").lower()
        forwarded_proto = (self.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip().lower()
        expected_scheme = forwarded_proto or ("https" if COOKIE_SECURE else "http")
        return bool(origin.scheme == expected_scheme and origin.netloc.lower() == host)

    def authenticated_user(self):
        token = get_session_token(self.headers)
        return auth_service.authenticate_session(token) if token else None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path == "/login":
            self.send_html(login_page(query.get("notice", [""])[0]))
            return
        if path == "/register":
            if not ALLOW_REGISTRATION:
                self.send_html("<h1>Registration is disabled.</h1>", 404)
                return
            self.send_html(register_page(query.get("notice", [""])[0]))
            return
        if AUTH_REQUIRED:
            try:
                user = self.authenticated_user()
            except Exception:
                self.send_html(auth_page("Service temporarily unavailable", "<p>Authentication storage is unavailable. Please try again later.</p>"), 503)
                return
            if user is None:
                self.redirect("/login")
                return
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
            self.send_html("<h1>Method not allowed</h1>", 405)
            return
        else:
            self.send_html("<h1>404</h1>", 404)
            return
        self.send_html(page)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 65536:
            self.send_html("<h1>Invalid request size</h1>", 413)
            return
        form = parse_form(self.rfile.read(length))

        if not self.same_origin_post():
            self.send_html("<h1>Cross-origin request blocked</h1>", 403)
            return

        if path == "/disconnect":
            if not self.is_local_dashboard_request():
                self.send_html("<h1>Local MT5 disconnect request required</h1>", 403)
                return
            SESSION.update({"connected": False, "account": None, "mode": None, "operating": False})
            mt5_service.shutdown()
            self.redirect("/")
            return

        if path == "/login":
            client_ip = self.client_address[0]
            if login_rate_limited(client_ip):
                self.send_html(login_page("Too many attempts. Try again in 15 minutes."), 429)
                return
            try:
                _user, token, _session = auth_service.login(
                    form.get("identifier", ""),
                    form.get("password", ""),
                )
                clear_login_failures(client_ip)
                self.redirect("/", build_session_cookie(token, secure=COOKIE_SECURE))
            except AuthenticationError:
                self.send_html(login_page("Invalid username/email or password."), 401)
            except Exception:
                self.send_html(auth_page("Service temporarily unavailable", "<p>Authentication storage is unavailable. Please try again later.</p>"), 503)
            return

        if path == "/register":
            if not ALLOW_REGISTRATION:
                self.send_html("<h1>Registration is disabled.</h1>", 404)
                return
            try:
                auth_service.register(
                    form.get("full_name", ""),
                    form.get("username", ""),
                    form.get("email", ""),
                    form.get("password", ""),
                )
                self.redirect("/login?notice=" + urllib.parse.quote("Account created. Sign in to continue."))
            except RegistrationError as exc:
                self.send_html(register_page(str(exc)), 400)
            except Exception:
                self.send_html(auth_page("Service temporarily unavailable", "<p>Account registration is temporarily unavailable.</p>"), 503)
            return

        if path == "/logout":
            token = get_session_token(self.headers)
            try:
                auth_service.logout(token or "")
            finally:
                self.redirect("/login", build_expired_session_cookie(secure=COOKIE_SECURE))
            return

        if AUTH_REQUIRED:
            try:
                if self.authenticated_user() is None:
                    self.redirect("/login")
                    return
            except Exception:
                self.send_html(auth_page("Service temporarily unavailable", "<p>Authentication storage is unavailable.</p>"), 503)
                return

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
            with DEMO_START_LOCK:
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
                        fundamental_bias=str(form.get("fundamental_bias") or "neutral").strip().lower(),
                        macro_bias_verified=form.get("confirm_macro_bias") == "yes",
                        high_impact_news=high_impact_news,
                        calendar_verified=calendar_verified,
                        explicit_confirmation=(
                            execute_demo and form.get("confirm_demo_order") == "yes"
                        ),
                        executor=executor,
                        account_balance=float(account.balance),
                        events=calendar_monitor.events_for_symbol(actual_symbol),
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
            login, password, server = parse_mt5_credentials(form)
            result = mt5_service.connect(
                login=login,
                password=password,
                server=server,
                requested_mode=mode,
                terminal_path=(form.get("terminal_path") or "").strip() or None,
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
    if AUTH_REQUIRED:
        try:
            # Verify PostgreSQL connectivity and the session table before
            # exposing an authenticated hosted service.
            auth_service.repository.find_session("0" * 64)
            alert_engine.get_all_alerts()
        except Exception as exc:
            raise RuntimeError(
                "Hosted mode requires a reachable PostgreSQL database with "
                "database/migrations/001_authentication.sql and "
                "database/migrations/002_persistent_alerts.sql applied."
            ) from exc
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
