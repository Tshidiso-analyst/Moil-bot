from pathlib import Path

import fitz


def extract_pdf_text(pdf_path: str) -> str:
    """
    Extract text from all pages of a PDF document.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        The extracted text as a single string.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If the supplied file is not a PDF.
    """
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {path.suffix}")

    pages = []

    with fitz.open(path) as document:
        for page in document:
            text = page.get_text("text").strip()

            if text:
                pages.append(text)

    return "\n\n".join(pages)
