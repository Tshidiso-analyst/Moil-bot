#!/usr/bin/env python3
"""Non-destructive verification for the dashboard Demo Start integration.

The dashboard integration is maintained directly in dashboard/app.py.
This legacy helper intentionally does not run git checkout, fetch, or rewrite
application files. It only verifies that the expected dry-run integration is
present in the current checkout.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.py"

REQUIRED_MARKERS = (
    "DemoStartController",
    '"/demo_start"',
    "START DEMO (DRY RUN)",
    "allow_execution=False",
)


def main() -> int:
    if not APP.is_file():
        print(f"Dashboard entrypoint not found: {APP}", file=sys.stderr)
        return 1

    source = APP.read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_MARKERS if marker not in source]
    if missing:
        print("Demo Start integration is incomplete:", file=sys.stderr)
        for marker in missing:
            print(f"  - Missing {marker!r}", file=sys.stderr)
        return 1

    print("Dashboard Demo Start integration is present.")
    print("Verified dry-run guard: allow_execution=False.")
    print("No files were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
