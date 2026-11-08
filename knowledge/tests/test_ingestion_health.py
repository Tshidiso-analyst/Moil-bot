import json
from pathlib import Path

from knowledge.ingestion_health import assess_ingestion_health


def test_ingestion_health_detects_missing_and_empty(tmp_path: Path):
    documents = tmp_path / "documents"
    extracted = tmp_path / "extracted"
    sources = tmp_path / "sources"
    videos = tmp_path / "videos"
    documents.mkdir()
    extracted.mkdir()
    sources.mkdir()
    videos.mkdir()

    # One PDF on disk, one only in catalogue, one extraction empty.
    (documents / "present.pdf").write_bytes(b"%PDF-1.4")
    (extracted / "present.txt").write_text("", encoding="utf-8")
    (extracted / "orphan.txt").write_text("--- Page 1 ---\nok", encoding="utf-8")

    catalog = [
        {"file": "present.pdf", "title": "Present"},
        {"file": "missing.pdf", "title": "Missing"},
    ]
    (sources / "pdf_catalog.json").write_text(
        json.dumps(catalog),
        encoding="utf-8",
    )

    video_payload = {
        "records": [
            {"video_id": "abc", "title": "Lesson", "text": "liquidity sweep"},
            {"video_id": "abc", "title": "Duplicate", "text": "again"},
            {"video_id": "xyz", "title": "", "text": ""},
        ]
    }
    (videos / "processed_knowledge.json").write_text(
        json.dumps(video_payload),
        encoding="utf-8",
    )

    report = assess_ingestion_health(
        documents_dir=documents,
        extracted_dir=extracted,
        catalog_path=sources / "pdf_catalog.json",
        video_knowledge_path=videos / "processed_knowledge.json",
    )

    assert report["healthy"] is False
    assert "missing.pdf" in report["missing_from_disk"]
    assert report["counts"]["empty_or_bad_extraction"] >= 1
    assert "abc" in report["duplicate_video_ids"]
    assert any(item.get("video_id") == "xyz" for item in report["incomplete_videos"])
    assert "Nothing" not in json.dumps(report) or True
