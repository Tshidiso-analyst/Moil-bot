import json

import pytest

from strategy.rule_registry import StrategyRuleRegistry


def make_registry(tmp_path, relevance="direct"):
    evidence_path = tmp_path / "evidence.json"
    review_path = tmp_path / "review.json"
    registry_path = tmp_path / "registry.json"

    evidence_path.write_text(json.dumps({
        "records": [{
            "evidence_id": "pdf-123",
            "source_type": "pdf",
            "title": "Risk Management Module",
            "locator": "page 7",
            "page": 7,
            "snippet": "Reviewed source passage.",
        }]
    }), encoding="utf-8")

    review_path.write_text(json.dumps({
        "assessments": [{
            "evidence_id": "pdf-123",
            "relevance": relevance,
        }]
    }), encoding="utf-8")

    return StrategyRuleRegistry(
        evidence_path=evidence_path,
        review_path=review_path,
        registry_path=registry_path,
        min_backtest_trades=100,
    )


def create_draft(registry):
    return registry.add_draft(
        rule_id="fvg-001",
        name="FVG candidate",
        concept="fair value gap",
        direction="bullish",
        entry_conditions=["Explicit entry condition from reviewed source."],
        invalidation_conditions=["Explicit invalidation condition."],
        exit_conditions=["Explicit exit condition."],
        risk_controls=["Maximum defined risk per trade."],
        evidence_ids=["pdf-123"],
        human_reviewed_evidence_ids=["pdf-123"],
    )


def test_draft_retains_source_and_never_enables_execution(tmp_path):
    registry = make_registry(tmp_path)
    rule = create_draft(registry)

    assert rule["status"] == "draft"
    assert rule["sources"][0]["page"] == 7
    assert rule["execution_enabled"] is False

    saved = json.loads(
        (tmp_path / "registry.json").read_text(encoding="utf-8")
    )
    assert saved["rules"][0]["rule_id"] == "fvg-001"


def test_source_must_be_confirmed_as_human_reviewed(tmp_path):
    registry = make_registry(tmp_path)

    with pytest.raises(ValueError, match="human-reviewed"):
        registry.add_draft(
            rule_id="fvg-001",
            name="FVG candidate",
            concept="fair value gap",
            direction="bullish",
            entry_conditions=["Entry"],
            invalidation_conditions=["Invalidation"],
            exit_conditions=["Exit"],
            risk_controls=["Risk limit"],
            evidence_ids=["pdf-123"],
            human_reviewed_evidence_ids=[],
        )


def test_weak_source_is_rejected(tmp_path):
    registry = make_registry(tmp_path, relevance="weak")

    with pytest.raises(ValueError, match="only weak relevance"):
        create_draft(registry)


def test_incomplete_backtest_does_not_pass_methodology_gate(tmp_path):
    registry = make_registry(tmp_path)
    create_draft(registry)

    result = registry.record_backtest("fvg-001", {
        "trade_count": 120,
        "costs_included": False,
        "out_of_sample": True,
        "no_future_leakage": True,
        "period_start": "2023-01-01",
        "period_end": "2025-01-01",
        "profit_factor": 1.2,
        "max_drawdown_pct": 12.0,
        "net_return_pct": 8.0,
    })

    assert result["methodology_gate"] == "not_passed"
    assert registry.all_rules()[0]["execution_enabled"] is False


def test_methodology_pass_still_does_not_enable_execution(tmp_path):
    registry = make_registry(tmp_path)
    create_draft(registry)

    result = registry.record_backtest("fvg-001", {
        "trade_count": 120,
        "costs_included": True,
        "out_of_sample": True,
        "no_future_leakage": True,
        "period_start": "2023-01-01",
        "period_end": "2025-01-01",
        "profit_factor": 1.2,
        "max_drawdown_pct": 12.0,
        "net_return_pct": 8.0,
    })

    assert result["methodology_gate"] == "passed"
    assert registry.all_rules()[0]["status"] == "draft"
    assert registry.all_rules()[0]["execution_enabled"] is False


def test_duplicate_rule_id_is_rejected(tmp_path):
    registry = make_registry(tmp_path)
    create_draft(registry)

    with pytest.raises(ValueError, match="already exists"):
        create_draft(registry)
