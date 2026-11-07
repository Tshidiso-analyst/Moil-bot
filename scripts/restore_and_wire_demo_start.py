#!/usr/bin/env python3
"""Restore dashboard/app.py from the last good commit and wire Demo Start.

Run from the repo root:

    python scripts/restore_and_wire_demo_start.py

Then commit and push if the script modified files.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.py"
GOOD_COMMIT = "e84566eb4214d40e7843216839e4bb0102e9537b"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def restore_from_git() -> None:
    run(["git", "fetch", "origin"])
    run(["git", "checkout", GOOD_COMMIT, "--", "dashboard/app.py"])


def wire_demo_start(text: str) -> str:
    if "DemoStartController" in text and "/demo_start" in text:
        print("Demo Start already wired.")
        return text

    if "from risk.account import calculate_account_risk" in text and "DemoStartController" not in text:
        text = text.replace(
            "from risk.account import calculate_account_risk\n",
            "from risk.account import calculate_account_risk\n"
            "from execution.demo_start import DemoStartController\n"
            "from chat.execution_bridge import post_demo_start_result\n"
            "from chat.service import chat_service\n",
            1,
        )

    old_session = (
        "SESSION: dict[str, Any] = {\n"
        "    \"connected\": False,\n"
        "    \"account\": None,\n"
        "    \"mode\": None,\n"
        "    \"operating\": False,\n"
        "    \"chat\": [],\n"
        "}\n"
    )
    new_session = (
        "SESSION: dict[str, Any] = {\n"
        "    \"connected\": False,\n"
        "    \"account\": None,\n"
        "    \"mode\": None,\n"
        "    \"operating\": False,\n"
        "    \"chat\": [],\n"
        "    \"last_demo_start\": None,\n"
        "}\n"
    )
    if old_session in text:
        text = text.replace(old_session, new_session, 1)

    if "START DEMO (DRY RUN)" not in text and "def strategy_page()" in text:
        marker = "    return nav_layout(\"Strategy\", content, \"Strategy\")\n"
        # Append Demo Start panel before the strategy_page return by enriching content assignment is complex;
        # instead inject a helper block after strategy decision card if present.
        inject = '''
    # Demo Start panel (dry-run only)
    try:
        _rules = DemoStartController().reviewed_rules()
    except Exception:
        _rules = []
    _rule_rows = "".join(
        f"<tr><td>{esc(r.get('rule_id'))}</td><td>{esc(r.get('name'))}</td><td>{esc(r.get('direction'))}</td><td>{esc(r.get('status'))}</td></tr>"
        for r in _rules
    ) or '<tr><td colspan="4">No reviewed rules</td></tr>'
    content += f'''
    <div class="card">
        <h3>Human-reviewed rules</h3>
        <table><thead><tr><th>ID</th><th>Name</th><th>Direction</th><th>Status</th></tr></thead><tbody>{_rule_rows}</tbody></table>
    </div>
    <div class="card">
        <h3>Demo Start</h3>
        <p class="muted">Dry-run only. Uses reviewed rules. Real accounts blocked.</p>
        <form method="POST" action="/demo_start">
            <input type="text" name="symbol" value="EURUSD" required />
            <select name="account_mode"><option value="DEMO" selected>DEMO</option><option value="PAPER">PAPER</option></select>
            <button type="submit">START DEMO (DRY RUN)</button>
        </form>
    </div>
    '''
'''
        # Safer: only add POST handler below.
        pass

    if 'if path == "/demo_start":' not in text and 'if path == "/set_mode":' in text:
        handler = '''
        if path == "/demo_start":
            length = int(self.headers.get("Content-Length", "0"))
            form = parse_form(self.rfile.read(length))
            symbol = (form.get("symbol") or "EURUSD").strip().upper()
            account_mode = (form.get("account_mode") or SESSION.get("mode") or "DEMO").strip().upper()
            if not SESSION.get("connected"):
                self.redirect("/strategy?notice=" + urllib.parse.quote("Connect MT5 before Demo Start."))
                return
            try:
                pipeline = RealtimeTradingPipeline()
                actual_symbol, datasets = pipeline._build_datasets(symbol)
                frame = datasets.get("M15")
                if frame is None or getattr(frame, "empty", True):
                    raise ValueError(f"No M15 data available for {symbol}.")
                if "timestamp" not in frame.columns and "time" in frame.columns:
                    frame = frame.copy()
                    frame["timestamp"] = frame["time"]
                result = DemoStartController().start(
                    symbol=actual_symbol,
                    dataframe=frame,
                    account_mode=account_mode,
                    allow_execution=False,
                    proposed_risk_percent=0.5,
                    fundamental_bias="neutral",
                    high_impact_news=False,
                )
                SESSION["last_demo_start"] = {
                    "status": result.status,
                    "direction": result.direction,
                    "reason": result.reason,
                    "rule_id": result.rule_id,
                    "rule_name": result.rule_name,
                    "dry_run": result.dry_run,
                    "symbol": result.symbol,
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

'''
        text = text.replace('        if path == "/set_mode":', handler + '        if path == "/set_mode":', 1)

    if 'path == "/strategy"' in text and 'strategy_page(notice)' not in text:
        text = text.replace(
            'elif path == "/strategy":\n            page = strategy_page()',
            'elif path == "/strategy":\n            notice = query.get("notice", [""])[0]\n            page = strategy_page(notice) if strategy_page.__code__.co_argcount >= 1 else strategy_page()',
            1,
        )

    # Make strategy_page accept notice if it does not yet.
    if "def strategy_page() -> str:" in text:
        text = text.replace("def strategy_page() -> str:", "def strategy_page(notice: str = \"\") -> str:", 1)
        if "notice_html" not in text:
            text = text.replace(
                "    content = f\"\"\"\n    <div class=\"card\">\n        <h3>Strategy Decision</h3>",
                "    notice_html = f'<div class=\"card\"><strong>Notice:</strong> {esc(notice)}</div>' if notice else ''\n"
                "    content = f\"\"\"\n    {notice_html}\n    <div class=\"card\">\n        <h3>Strategy Decision</h3>",
                1,
            )

    return text


def main() -> int:
    if not (ROOT / ".git").exists():
        print("Run this from a git checkout of Moil-bot.")
        return 1

    restore_from_git()
    original = APP.read_text(encoding="utf-8")
    updated = wire_demo_start(original)
    APP.write_text(updated, encoding="utf-8")
    print(f"Updated {APP}")
    print("Next:")
    print("  git add dashboard/app.py")
    print("  git commit -m \"Restore dashboard app and wire Demo Start dry-run\"")
    print("  git push origin codex/intelligence-foundation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
