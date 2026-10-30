import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "documents"
SOURCE_FILE = ROOT / "sources" / "pdf_urls.csv"
CATALOG_FILE = ROOT / "sources" / "pdf_catalog.json"

PDF_DIR.mkdir(parents=True, exist_ok=True)

def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", "_", value).strip("._ ")
    return (value[:120] or "document")

def main():
    if not SOURCE_FILE.exists():
        print(f"Missing source list: {SOURCE_FILE}")
        return

    with SOURCE_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        sources = list(csv.DictReader(f))

    catalog = []
    downloaded = 0
    skipped = 0
    failed = 0

    for number, item in enumerate(sources, start=1):
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        source_url = (item.get("source_url") or "").strip()
        license_name = (item.get("license") or "").strip()
        permission = (item.get("redistribution_allowed") or "").strip().lower()

        if not title or not url:
            continue

        if permission not in ("yes", "public domain", "cc0"):
            print(f"[SKIP] {title}: redistribution permission not confirmed")
            skipped += 1
            continue

        if urlparse(url).scheme != "https":
            print(f"[SKIP] {title}: only HTTPS URLs are accepted")
            skipped += 1
            continue

        filename = safe_name(title) + ".pdf"
        destination = PDF_DIR / filename

        if destination.exists():
            if destination.read_bytes()[:5] == b"%PDF-":
                print(f"[EXISTS] {filename}")
                downloaded += 1
                catalog.append({
                    "title": title,
                    "file": filename,
                    "source_url": source_url or url,
                    "download_url": url,
                    "license": license_name,
                    "redistribution_allowed": permission
                })
                continue

            destination.unlink()

        try:
            print(f"[{number}/{len(sources)}] Downloading: {title}")
            response = requests.get(
                url,
                timeout=45,
                headers={"User-Agent": "Moil-bot-PDF-Library/1.0"},
                allow_redirects=True,
                stream=True
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            first_chunk = next(response.iter_content(chunk_size=8192), b"")

            if not first_chunk.startswith(b"%PDF-"):
                print(f"[FAILED] Response is not a PDF: {title} ({content_type})")
                failed += 1
                response.close()
                continue

            with destination.open("wb") as out:
                out.write(first_chunk)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        out.write(chunk)

            response.close()

            catalog.append({
                "title": title,
                "file": filename,
                "source_url": source_url or url,
                "download_url": url,
                "license": license_name,
                "redistribution_allowed": permission,
                "bytes": destination.stat().st_size
            })
            downloaded += 1
            print(f"[OK] Saved {filename}")
            time.sleep(1)

        except Exception as exc:
            if destination.exists():
                destination.unlink()
            print(f"[FAILED] {title}: {exc}")
            failed += 1

    CATALOG_FILE.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\n===== PDF LIBRARY SUMMARY =====")
    print(f"Valid PDFs recorded: {downloaded}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")
    print(f"Catalogue: {CATALOG_FILE}")
    print(f"PDF folder: {PDF_DIR}")

if __name__ == "__main__":
    main()
