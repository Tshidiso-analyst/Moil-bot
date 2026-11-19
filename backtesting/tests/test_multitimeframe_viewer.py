import json

import pandas as pd
import pytest

from backtesting.multitimeframe_candidate import _closed, make_multitimeframe_signal
from backtesting.replay_viewer import build_viewer


def frame(start, periods, freq):
    times = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    return pd.DataFrame({
        "timestamp": times, "open": [100.0] * periods,
        "high": [101.0] * periods, "low": [99.0] * periods,
        "close": [100.0] * periods,
    })


def test_htf_candle_not_visible_until_its_close():
    h1 = frame("2026-01-01", 3, "h")
    known = _closed(h1, pd.Timestamp("2026-01-01T01:00:00Z"), "H1")
    assert len(known) == 1
    assert known[0]["timestamp"] == pd.Timestamp("2026-01-01T00:00:00Z")


def test_multitimeframe_candidate_fails_closed_without_structure():
    frames = {
        "D1": frame("2025-11-01", 50, "D"),
        "H4": frame("2025-12-01", 50, "4h"),
        "H1": frame("2025-12-01", 50, "h"),
        "M15": frame("2025-12-01", 50, "15min"),
    }
    signal = make_multitimeframe_signal({"EURUSD": frames})
    assert signal("EURUSD", frames["M15"]) is None


def test_multitimeframe_requires_all_four_timeframes():
    with pytest.raises(ValueError, match="require D1/H4/H1/M15"):
        make_multitimeframe_signal({"EURUSD": {"M15": frame("2026-01-01", 30, "15min")}})


def test_offline_viewer_writes_playback_controls(tmp_path):
    data = frame("2026-01-01", 3, "15min")
    eu, gold = tmp_path / "eurusd.csv", tmp_path / "gold.csv"
    data.to_csv(eu, index=False)
    data.to_csv(gold, index=False)
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({
        "starting_zar": 500, "events": [], "closed_trades": []
    }))
    output = tmp_path / "viewer.html"
    build_viewer(eu, gold, ledger, output)
    text = output.read_text()
    assert "SIMULATED HISTORICAL FILLS" in text
    assert 'id="play"' in text
    assert "EURUSD" in text and "XAUUSD" in text
