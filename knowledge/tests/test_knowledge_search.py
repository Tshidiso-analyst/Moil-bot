import json

from knowledge.search import search_knowledge


def test_search_finds_concept_and_source_video(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps({
            "records": [{
                "title": "Liquidity Sweep Review",
                "video_id": "abc123",
                "url": "https://www.youtube.com/watch?v=abc123",
                "concepts": ["liquidity sweep"],
                "text": "Price sweeps liquidity before reversing.",
            }]
        }),
        encoding="utf-8",
    )

    results = search_knowledge("liquidity sweep", path=path)

    assert len(results) == 1
    assert results[0]["video_id"] == "abc123"
    assert results[0]["title"] == "Liquidity Sweep Review"
    assert results[0]["score"] > 0


def test_search_returns_empty_for_blank_or_unknown_query(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text(json.dumps({"records": []}), encoding="utf-8")

    assert search_knowledge("", path=path) == []
    assert search_knowledge("unknown concept", path=path) == []


def test_search_respects_limit(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps({
            "records": [
                {
                    "title": f"Liquidity Lesson {number}",
                    "video_id": f"video{number}",
                    "url": f"https://www.youtube.com/watch?v=video{number}",
                    "concepts": ["liquidity"],
                    "text": "Liquidity is discussed.",
                }
                for number in range(3)
            ]
        }),
        encoding="utf-8",
    )

    assert len(search_knowledge("liquidity", limit=2, path=path)) == 2


def test_search_rejects_invalid_limit(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text(json.dumps({"records": []}), encoding="utf-8")

    try:
        search_knowledge("liquidity", limit=0, path=path)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for limit=0")

def test_exact_concept_match_ranks_above_transcript_only_match(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps({
            "records": [
                {
                    "title": "General Trading Discussion",
                    "video_id": "mention123",
                    "url": "https://www.youtube.com/watch?v=mention123",
                    "concepts": ["market structure"],
                    "text": "The trader discusses a liquidity sweep before entry.",
                },
                {
                    "title": "Liquidity Sweep Lesson",
                    "video_id": "concept123",
                    "url": "https://www.youtube.com/watch?v=concept123",
                    "concepts": ["liquidity sweep"],
                    "text": "The lesson explains how a liquidity sweep forms.",
                },
            ]
        }),
        encoding="utf-8",
    )

    results = search_knowledge("liquidity sweep", path=path)

    assert len(results) == 2
    assert results[0]["video_id"] == "concept123"


def test_search_result_keeps_relevant_source_fields(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps({
            "records": [{
                "title": "Fair Value Gap Lesson",
                "video_id": "fvg123",
                "url": "https://www.youtube.com/watch?v=fvg123",
                "concepts": ["fair value gap"],
                "text": "Price returns to the fair value gap before moving higher.",
            }]
        }),
        encoding="utf-8",
    )

    results = search_knowledge("fair value gap", path=path)

    assert len(results) == 1
    assert results[0]["title"] == "Fair Value Gap Lesson"
    assert results[0]["video_id"] == "fvg123"
    assert results[0]["url"].endswith("v=fvg123")
    assert results[0]["concepts"] == ["fair value gap"]
    assert results[0]["snippet"]
    assert results[0]["score"] > 0
import json


def test_tutorial_ranks_above_similar_trade_review(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps({
            "records": [
                {
                    "title": "Fair Value Gap Trade Review",
                    "video_id": "review123",
                    "url": "https://www.youtube.com/watch?v=review123",
                    "concepts": ["fair value gap"],
                    "text": "Fair value gap explained with an example.",
                },
                {
                    "title": "Fair Value Gap Tutorial",
                    "video_id": "lesson123",
                    "url": "https://www.youtube.com/watch?v=lesson123",
                    "concepts": ["fair value gap"],
                    "text": "Fair value gap explained with an example.",
                },
            ]
        }),
        encoding="utf-8",
    )

    results = search_knowledge("fair value gap", path=path)

    assert results[0]["video_id"] == "lesson123"


def test_search_handles_comma_separated_concepts(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text(
        json.dumps({
            "records": [{
                "title": "Order Block Discussion",
                "video_id": "order123",
                "url": "https://www.youtube.com/watch?v=order123",
                "concepts": ["order block,resistance"],
                "text": "A discussion of trading concepts.",
            }]
        }),
        encoding="utf-8",
    )

    results = search_knowledge("order block", path=path)

    assert len(results) == 1
    assert "order block" in results[0]["concepts"]
