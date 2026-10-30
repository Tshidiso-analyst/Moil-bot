import json
import re
from pathlib import Path

try:
    import fitz
except ImportError:
    print("PyMuPDF is missing. Install it with:")
    print("python -m pip install pymupdf")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "documents"
OUT_DIR = ROOT / "extracted"
CATALOG_PATH = ROOT / "sources" / "pdf_catalog.json"
REPORT_PATH = OUT_DIR / "extraction_report.json"

OUT_DIR.mkdir(parents=True, exist_ok=True)

report = []
pdf_files = sorted(PDF_DIR.glob("*.pdf"))

for pdf_path in pdf_files:
    output_path = OUT_DIR / f"{pdf_path.stem}.txt"

    try:
        with fitz.open(pdf_path) as doc:
            pages = []
            for page_number, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if text:
                    pages.append(f"--- Page {page_number} ---\n{text}")

            full_text = "\n\n".join(pages)
            output_path.write_text(full_text, encoding="utf-8")

            item = {
                "file": pdf_path.name,
                "text_file": output_path.name,
                "pages": len(doc),
                "characters": len(full_text),
                "status": "ok" if full_text else "no_text_found"
            }
            report.append(item)

            print(
                f"[{item['status'].upper()}] {pdf_path.name} | "
                f"{item['pages']} pages | {item['characters']} characters"
            )

    except Exception as exc:
        report.append({
            "file": pdf_path.name,
            "status": "error",
            "error": str(exc)
        })
        print(f"[ERROR] {pdf_path.name}: {exc}")

REPORT_PATH.write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("\n===== EXTRACTION SUMMARY =====")
print(f"PDF files found: {len(pdf_files)}")
print(f"Successfully extracted: {sum(x['status'] == 'ok' for x in report)}")
print(f"PDFs with no extractable text: {sum(x['status'] == 'no_text_found' for x in report)}")
print(f"Errors: {sum(x['status'] == 'error' for x in report)}")
print(f"Text folder: {OUT_DIR}")
print(f"Report: {REPORT_PATH}")
