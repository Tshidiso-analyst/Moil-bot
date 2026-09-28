from pathlib import Path

import fitz

from knowledge.documents.pdf_extractor import extract_pdf_text


def test_extract_pdf_text(tmp_path: Path):
    pdf_path = tmp_path / "sample.pdf"

    document = fitz.open()

    page = document.new_page()
    page.insert_text((72, 72), "Moil Bot Knowledge Engine")

    document.save(pdf_path)
    document.close()

    text = extract_pdf_text(str(pdf_path))

    assert "Moil Bot Knowledge Engine" in text
