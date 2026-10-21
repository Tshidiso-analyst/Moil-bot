import json

import fitz
import pytest

from knowledge.unified_search import search_all_knowledge


def test_search_returns_matching_video_and_pdf_page(tmp_path):
    video_path = tmp_path / "processed_knowledge.json"
    video_path.write_text(json.dumps({"records": [{
        "title": "Liquidity Sweep Lesson",
        "video_id": "lesson123",
        "url": "https://www.youtube.com/watch?v=lesson123",
        "concepts": ["liquidity sweep"],
        "text": "A liquidity sweep takes liquidity before a reversal.",
    }]}), encoding="utf-8")

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    pdf_path = pdf_dir / "ict-notes.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "A liquidity sweep can occur above prior highs.")
    document.save(pdf_path)
    document.close()

    results = search_all_knowledge(
        "liquidity sweep",
        video_knowledge_path=video_path,
        pdf_directory=pdf_dir,
    )

    assert {result["source_type"] for result in results} == {"video", "pdf"}
    video = next(result for result in results if result["source_type"] == "video")
    pdf = next(result for result in results if result["source_type"] == "pdf")
    assert video["url"].endswith("v=lesson123")
    assert video["video_id"] == "lesson123"
    assert pdf["page"] == 1
    assert pdf["location"].endswith("ict-notes.pdf")
    assert "liquidity sweep" in pdf["snippet"].lower()


def test_search_ignores_blank_and_unknown_queries(tmp_path):
    empty_path = tmp_path / "processed_knowledge.json"
    empty_path.write_text(json.dumps({"records": []}), encoding="utf-8")
    assert search_all_knowledge("  ", video_knowledge_path=empty_path, pdf_directory=tmp_path) == []
    assert search_all_knowledge("unknownterm", video_knowledge_path=empty_path, pdf_directory=tmp_path) == []


def test_search_validates_limit(tmp_path):
    with pytest.raises(ValueError, match="positive integer"):
        search_all_knowledge("liquidity", limit=0, video_knowledge_path=tmp_path / "missing.json", pdf_directory=tmp_path)


def test_search_diversifies_results_across_pdfs(tmp_path):
    video_path = tmp_path / "processed_knowledge.json"
    video_path.write_text(
        json.dumps({"records": []}),
        encoding="utf-8",
    )

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()

    # The first PDF has several matching pages.
    first_pdf = fitz.open()
    for page_number in range(3):
        page = first_pdf.new_page()
        page.insert_text(
            (72, 72),
            f"Liquidity concepts and market structure, page {page_number + 1}.",
        )
    first_pdf.save(pdf_dir / "A_Notes.pdf")
    first_pdf.close()

    # A second relevant PDF should also get a chance to appear.
    second_pdf = fitz.open()
    page = second_pdf.new_page()
    page.insert_text(
        (72, 72),
        "Liquidity concepts and trading decisions.",
    )
    second_pdf.save(pdf_dir / "B_Notes.pdf")
    second_pdf.close()

    results = search_all_knowledge(
        "liquidity",
        limit=3,
        video_knowledge_path=video_path,
        pdf_directory=pdf_dir,
    )

    first_pdf_results = [
        result for result in results
        if result["title"] == "A Notes"
    ]

    assert len(results) == 3
    assert len(first_pdf_results) <= 2
    assert any(result["title"] == "B Notes" for result in results)


def test_search_single_pdf_can_return_multiple_pages(tmp_path):
    video_path = tmp_path / "processed_knowledge.json"
    video_path.write_text(
        json.dumps({"records": []}),
        encoding="utf-8",
    )

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()

    document = fitz.open()
    for page_number in range(3):
        page = document.new_page()
        page.insert_text(
            (72, 72),
            f"Liquidity concepts explained on page {page_number + 1}.",
        )
    document.save(pdf_dir / "Only_Notes.pdf")
    document.close()

    results = search_all_knowledge(
        "liquidity",
        limit=3,
        video_knowledge_path=video_path,
        pdf_directory=pdf_dir,
    )

    assert len(results) == 3
    assert all(result["source_type"] == "pdf" for result in results)
    assert [result["page"] for result in results] == [1, 2, 3]


def test_search_diversifies_pdf_results_when_other_sources_match(tmp_path):
    video_path = tmp_path / "processed_knowledge.json"
    video_path.write_text(json.dumps({"records": [{
        "title": "Risk Management Video",
        "video_id": "risk123",
        "url": "https://www.youtube.com/watch?v=risk123",
        "concepts": ["risk management"],
        "text": "Risk management helps traders control losses.",
    }]}), encoding="utf-8")

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()

    def create_pdf(filename, page_count):
        document = fitz.open()
        for _ in range(page_count):
            page = document.new_page()
            page.insert_text(
                (72, 72),
                "Risk management helps traders control risk before every trade.",
            )
        document.save(pdf_dir / filename)
        document.close()

    create_pdf("alpha-notes.pdf", 4)
    create_pdf("beta-notes.pdf", 1)
    create_pdf("gamma-notes.pdf", 1)

    results = search_all_knowledge(
        "risk management",
        limit=5,
        video_knowledge_path=video_path,
        pdf_directory=pdf_dir,
    )

    assert len(results) == 5
    alpha_results = [
        result for result in results
        if result["title"] == "alpha notes"
    ]
    assert len(alpha_results) <= 2
    assert any(result["source_type"] == "video" for result in results)
    assert any(result["title"] == "beta notes" for result in results)
    assert any(result["title"] == "gamma notes" for result in results)


def test_search_can_return_multiple_pages_from_only_one_pdf(tmp_path):
    video_path = tmp_path / "empty_knowledge.json"
    video_path.write_text(
        json.dumps({"records": []}),
        encoding="utf-8",
    )

    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()

    document = fitz.open()
    for _ in range(4):
        page = document.new_page()
        page.insert_text(
            (72, 72),
            "Risk management helps traders control risk before every trade.",
        )
    document.save(pdf_dir / "risk-notes.pdf")
    document.close()

    results = search_all_knowledge(
        "risk management",
        limit=5,
        video_knowledge_path=video_path,
        pdf_directory=pdf_dir,
    )

    assert len(results) == 4
    assert all(result["source_type"] == "pdf" for result in results)
