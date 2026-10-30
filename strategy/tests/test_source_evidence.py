import json

import pytest

from strategy.source_evidence import (
    collect_source_evidence,
    write_source_evidence,
)


def test_collects_realistic_pdf_and_video_provenance():
    def search(query, limit=8):
        return [
            {
                "source_type": "pdf",
                "title": "Risk Management Module",
                "page": 7,
                "snippet": "Risk sizing and invalidation passage.",
                "score": 80,
            },
            {
                "source_type": "video",
                "title": "Fair Value Gap Lesson",
                "video_id": "abc123",
                "url": "https://www.youtube.com/watch?v=abc123",
                "snippet": "A video transcript passage.",
                "score": 90,
            },
        ]

    report = collect_source_evidence(
        search_fn=search,
        queries=("liquidity", "risk management"),
        limit=3,
    )

    assert report["record_count"] == 2
    assert report["source_counts"] == {"pdf": 1, "video": 1}
    assert all(r["review_status"] == "unreviewed" for r in report["records"])
    assert all(
        r["rule_status"] == "not_yet_extracted_or_validated"
        for r in report["records"]
    )

    pdf = next(r for r in report["records"] if r["source_type"] == "pdf")
    video = next(r for r in report["records"] if r["source_type"] == "video")

    assert pdf["locator"] == "page 7"
    assert video["video_id"] == "abc123"


def test_duplicate_passage_merges_matched_queries():
    passage = {
        "source_type": "pdf",
        "title": "Risk Module",
        "page": 3,
        "snippet": "Keep risk within the defined account limit.",
        "score": 20,
    }

    def search(query, limit=8):
        return [passage, dict(passage)]

    report = collect_source_evidence(
        search_fn=search,
        queries=("risk management", "position sizing"),
    )

    assert report["record_count"] == 1
    assert report["records"][0]["matched_queries"] == [
        "risk management",
        "position sizing",
    ]


def test_search_errors_are_reported_and_other_queries_continue():
    def search(query, limit=8):
        if query == "broken":
            raise OSError("test search failure")
        return [{
            "source_type": "video",
            "title": "Lesson",
            "video_id": "xyz123",
            "snippet": "Source passage.",
        }]

    report = collect_source_evidence(
        search_fn=search,
        queries=("broken", "working"),
    )

    assert report["record_count"] == 1
    assert len(report["errors"]) == 1
    assert report["errors"][0]["query"] == "broken"


def test_invalid_limit_is_rejected():
    with pytest.raises(ValueError, match="positive integer"):
        collect_source_evidence(
            search_fn=lambda query, limit=8: [],
            limit=0,
        )


def test_report_is_written_as_json(tmp_path):
    output = tmp_path / "reports" / "source_evidence.json"

    report = write_source_evidence(
        output_path=output,
        search_fn=lambda query, limit=8: [],
        queries=("liquidity",),
    )

    saved = json.loads(output.read_text(encoding="utf-8"))

    assert report["record_count"] == 0
    assert saved["queries"] == ["liquidity"]
    assert saved["records"] == []
