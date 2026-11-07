from chat.knowledge_bridge import format_evidence_citations, format_ingestion_health


def test_format_evidence_citations_includes_source_locators():
    results = [
        {
            "source_type": "pdf",
            "title": "ICT Notes",
            "page": 12,
            "snippet": "A fair value gap forms after displacement.",
        },
        {
            "source_type": "video",
            "title": "Liquidity Lesson",
            "video_id": "abc123",
            "snippet": "Buy-side liquidity above equal highs.",
        },
    ]
    text = format_evidence_citations(results, query="fair value gap")
    assert "PDF · ICT Notes · page 12" in text
    assert "Video · Liquidity Lesson · abc123" in text
    assert "not approved rules" in text.lower()


def test_format_ingestion_health_lists_issues():
    report = {
        "status": "needs_attention",
        "counts": {"pdf_files": 2, "extracted_files": 1, "video_records": 3},
        "missing_from_disk": ["a.pdf"],
        "missing_extraction": [],
        "empty_or_bad_extraction": [{"file": "b.txt"}],
        "incomplete_videos": [],
        "duplicate_video_ids": [],
        "catalog_errors": [],
        "video_errors": [],
    }
    text = format_ingestion_health(report)
    assert "needs_attention" in text
    assert "Missing PDF files: 1" in text
    assert "does not approve" in text.lower() or "approves" in text.lower()
