# Restore dashboard/app.py

If `dashboard/app.py` was overwritten by a bad push, restore the last good version:

```bash
git fetch origin
git checkout e84566eb4214d40e7843216839e4bb0102e9537b -- dashboard/app.py
git add dashboard/app.py
git commit -m "Restore dashboard/app.py from last good revision"
git push origin codex/intelligence-foundation
```

Then wire Demo Start using `dashboard/demo_start_ui.py` helpers on the Strategy page.

The human-reviewed rule `ny_fvg_liq_sweep_v1` remains in `knowledge/reports/strategy_rule_registry.json`.
