from strategy.source_review import assess_passage, review_catalogue


def test_irrelevant_seasonal_commentary_does_not_pass_market_structure():
    record = {
        "title": "How New Students Should Start Part 1",
        "snippet": "Seasonal tendencies and holiday economic drivers.",
    }

    result = assess_passage(
        record,
        "market structure higher highs higher lows",
    )

    assert result["relevance"] == "weak"


def test_fair_value_gap_with_entry_context_is_direct_candidate():
    record = {
        "title": "Fair Value Gap Entry Lesson",
        "snippet": (
            "The fair value gap formed after displacement. "
            "Wait for mitigation before the entry."
        ),
    }

    result = assess_passage(record, "fair value gap entry conditions")

    assert result["relevance"] == "direct"
    assert "fair value gap" in result["matched_terms"]


def test_risk_module_heading_alone_is_not_direct_evidence():
    record = {
        "title": "Risk Management Module",
        "snippet": "Table of contents. Complete study program.",
    }

    result = assess_passage(record, "risk management position sizing")

    assert result["relevance"] == "partial"


def test_review_catalogue_keeps_rules_unapproved(tmp_path):
    import json

    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({
        "records": [{
            "evidence_id": "e1",
            "source_type": "video",
            "title": "A lesson",
            "snippet": "Seasonal tendency commentary.",
            "matched_queries": [
                "market structure higher highs higher lows"
            ],
        }]
    }), encoding="utf-8")

    report = review_catalogue(path)

    assert report["input_record_count"] == 1
    assert report["assessments"][0]["relevance"] == "weak"
    assert report["assessments"][0]["rule_status"] == "not_approved"
