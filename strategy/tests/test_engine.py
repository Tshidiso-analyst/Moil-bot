from types import SimpleNamespace

import pandas as pd
import pytest

import strategy.engine as strategy_module
from analysis.smc_patterns import FairValueGap
from strategy.engine import StrategyEngine


def make_datasets():
    frame = pd.DataFrame({
        "open":  [1.0, 1.1, 1.2],
        "high":  [1.1, 1.2, 1.3],
        "low":   [0.9, 1.0, 1.15],
        "close": [1.05, 1.15, 1.25],
    })
    return {"H1": frame.copy(), "M15": frame.copy()}


def source_results():
    return [
        {
            "source_type": "pdf",
            "title": "Risk Management Module",
            "page": 7,
            "snippet": "Risk management source passage.",
            "score": 80,
        },
        {
            "source_type": "video",
            "title": "Fair Value Gap Lesson",
            "video_id": "abc123",
            "url": "https://www.youtube.com/watch?v=abc123",
            "snippet": "Video source passage.",
            "score": 90,
        },
    ]


def install_analysis_stubs(monkeypatch, alignment="bullish", gap_direction="bullish"):
    class FakeTopDown:
        def analyse(self, datasets):
            trends = {
                timeframe: (
                    "bullish" if alignment == "bullish"
                    else "bearish" if alignment == "bearish"
                    else ("bullish" if timeframe == "H1" else "bearish")
                )
                for timeframe in datasets
            }
            analyses = [
                SimpleNamespace(timeframe=tf, trend=trend)
                for tf, trend in trends.items()
            ]
            return SimpleNamespace(
                alignment=alignment,
                analyses=analyses,
            )

    monkeypatch.setattr(strategy_module, "TopDownAnalyzer", FakeTopDown)

    def fake_gaps(dataframe):
        if gap_direction is None:
            return []
        return [
            FairValueGap(
                index=len(dataframe) - 1,
                direction=gap_direction,
                lower=1.1,
                upper=1.2,
            )
        ]

    monkeypatch.setattr(strategy_module, "find_fair_value_gaps", fake_gaps)


def test_source_backed_technical_candidate_is_research_only(monkeypatch):
    install_analysis_stubs(monkeypatch)

    engine = StrategyEngine(source_search=lambda query, limit=4: source_results())
    decision = engine.evaluate(
        symbol="EURUSD",
        datasets=make_datasets(),
        fundamental_bias="neutral",
        execution_timeframe="M15",
    )

    assert decision.status == "research_candidate"
    assert decision.direction == "bullish"
    assert decision.source_rule_status == "source_passages_found_rules_unvalidated"
    assert {item.source_type for item in decision.source_passages} == {"pdf", "video"}
    assert any(item.locator == "page 7" for item in decision.source_passages)
    assert any("abc123" in item.locator for item in decision.source_passages)
    assert decision.backtest_ready is False
    assert decision.execution_ready is False


def test_conflicting_fundamental_bias_rejects_candidate(monkeypatch):
    install_analysis_stubs(monkeypatch)

    engine = StrategyEngine(source_search=lambda query, limit=4: source_results())
    decision = engine.evaluate(
        "EURUSD",
        make_datasets(),
        fundamental_bias="bearish",
    )

    assert decision.status == "rejected"
    assert any("conflicts" in reason for reason in decision.reasons)
    assert decision.execution_ready is False


def test_both_source_types_are_required(monkeypatch):
    install_analysis_stubs(monkeypatch)

    only_video = [source_results()[1]]
    engine = StrategyEngine(source_search=lambda query, limit=4: only_video)
    decision = engine.evaluate("EURUSD", make_datasets())

    assert decision.status == "needs_source_evidence"
    assert decision.source_rule_status == "incomplete_source_coverage"
    assert decision.execution_ready is False


def test_mixed_timeframes_do_not_qualify(monkeypatch):
    install_analysis_stubs(
        monkeypatch,
        alignment="mixed",
        gap_direction="bullish",
    )

    engine = StrategyEngine(source_search=lambda query, limit=4: source_results())
    decision = engine.evaluate("EURUSD", make_datasets())

    assert decision.status == "rejected"
    assert decision.direction == "neutral"
    assert decision.execution_ready is False


def test_invalid_fundamental_bias_is_rejected():
    engine = StrategyEngine(source_search=lambda query, limit=4: [])
    with pytest.raises(ValueError, match="fundamental_bias"):
        engine.evaluate(
            "EURUSD",
            make_datasets(),
            fundamental_bias="very bullish",
        )


def test_unknown_execution_timeframe_is_rejected(monkeypatch):
    install_analysis_stubs(monkeypatch)
    engine = StrategyEngine(source_search=lambda query, limit=4: source_results())

    with pytest.raises(ValueError, match="Unknown execution timeframe"):
        engine.evaluate(
            "EURUSD",
            make_datasets(),
            execution_timeframe="M5",
        )
