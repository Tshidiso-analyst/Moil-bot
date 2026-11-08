from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

KNOWLEDGE_ROOT = Path(__file__).resolve().parent
DOCUMENTS_DIR = KNOWLEDGE_ROOT / "documents"
EXTRACTED_DIR = KNOWLEDGE_ROOT / "extracted"
SOURCES_DIR = KNOWLEDGE_ROOT / "sources"
VIDEOS_DIR = KNOWLEDGE_ROOT / "videos"
CATALOG_PATH = SOURCES_DIR / "pdf_catalog.json"
VIDEO_KNOWLEDGE_PATH = VIDEOS_DIR / "processed_knowledge.json"
DEFAULT_REPORT_PATH = KNOWLEDGE_ROOT / "reports" / "ingestion_health.json"


def _load_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _pdf_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )


def _extracted_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.glob("*.txt")
        if path.name != "__init__.py"
    )


def assess_ingestion_health(
    *,
    documents_dir: Path | str = DOCUMENTS_DIR,
    extracted_dir: Path | str = EXTRACTED_DIR,
    catalog_path: Path | str = CATALOG_PATH,
    video_knowledge_path: Path | str = VIDEO_KNOWLEDGE_PATH,
) -> dict:
    """Report PDF/video source health without marking anything as learned or approved.

    Detects missing files, empty extractions, catalogue mismatches, and video
    catalogue problems. Matching text is never treated as an approved rule.
    """
    documents_dir = Path(documents_dir)
    extracted_dir = Path(extracted_dir)
    catalog_path = Path(catalog_path)
    video_knowledge_path = Path(video_knowledge_path)

    pdfs = _pdf_files(documents_dir)
    extracted = _extracted_files(extracted_dir)
    catalog = _load_json(catalog_path)

    catalog_files: list[str] = []
    catalog_errors: list[str] = []
    if catalog is None:
        catalog_errors.append("pdf_catalog.json is missing or unreadable")
    elif not isinstance(catalog, list):
        catalog_errors.append("pdf_catalog.json must be a list of source records")
    else:
        for item in catalog:
            if not isinstance(item, dict):
                catalog_errors.append("catalogue contains a non-object entry")
                continue
            name = str(item.get("file") or "").strip()
            if not name:
                catalog_errors.append("catalogue entry is missing file name")
                continue
            catalog_files.append(name)

    pdf_names = {path.name for path in pdfs}
    extracted_stems = {path.stem for path in extracted}
    catalog_set = set(catalog_files)

    missing_from_disk = sorted(catalog_set - pdf_names)
    uncatalogued_pdfs = sorted(pdf_names - catalog_set)
    missing_extraction = sorted(
        path.stem for path in pdfs if path.stem not in extracted_stems
    )
    orphan_extractions = sorted(
        path.name for path in extracted if path.stem not in {p.stem for p in pdfs}
    )

    empty_extractions = []
    for path in extracted:
        try:
            text = path.read_text(encoding="utf-8-sig").strip()
        except OSError as exc:
            empty_extractions.append({"file": path.name, "reason": f"read_error: {exc}"})
            continue
        if not text:
            empty_extractions.append({"file": path.name, "reason": "empty_text"})
        elif "--- Page " not in text:
            empty_extractions.append({"file": path.name, "reason": "missing_page_markers"})

    video_errors: list[str] = []
    video_records = []
    video_data = _load_json(video_knowledge_path)
    if video_data is None:
        video_errors.append("processed_knowledge.json is missing or unreadable")
    elif not isinstance(video_data, dict):
        video_errors.append("processed_knowledge.json must be an object")
    else:
        raw = video_data.get("records", [])
        if not isinstance(raw, list):
            video_errors.append("video records must be a list")
        else:
            for item in raw:
                if not isinstance(item, dict):
                    video_errors.append("video catalogue contains a non-object entry")
                    continue
                video_records.append(item)

    incomplete_videos = []
    seen_video_ids: set[str] = set()
    duplicate_video_ids: list[str] = []
    for item in video_records:
        video_id = str(item.get("video_id") or "").strip()
        title = str(item.get("title") or "").strip()
        text = str(item.get("text") or "").strip()
        if video_id:
            if video_id in seen_video_ids:
                duplicate_video_ids.append(video_id)
            seen_video_ids.add(video_id)
        if not title or not text:
            incomplete_videos.append(
                {
                    "video_id": video_id or None,
                    "title": title or None,
                    "reason": "missing_title_or_transcript",
                }
            )

    status_counts = Counter()
    status_counts["pdf_files"] = len(pdfs)
    status_counts["extracted_files"] = len(extracted)
    status_counts["catalog_entries"] = len(catalog_files)
    status_counts["video_records"] = len(video_records)
    status_counts["missing_from_disk"] = len(missing_from_disk)
    status_counts["uncatalogued_pdfs"] = len(uncatalogued_pdfs)
    status_counts["missing_extraction"] = len(missing_extraction)
    status_counts["empty_or_bad_extraction"] = len(empty_extractions)
    status_counts["incomplete_videos"] = len(incomplete_videos)
    status_counts["duplicate_video_ids"] = len(duplicate_video_ids)

    healthy = (
        not catalog_errors
        and not video_errors
        and not missing_from_disk
        and not missing_extraction
        and not empty_extractions
        and not incomplete_videos
        and not duplicate_video_ids
        and (len(pdfs) > 0 or len(video_records) > 0)
    )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "healthy": healthy,
        "status": "healthy" if healthy else "needs_attention",
        "counts": dict(status_counts),
        "catalog_errors": catalog_errors,
        "video_errors": video_errors,
        "missing_from_disk": missing_from_disk,
        "uncatalogued_pdfs": uncatalogued_pdfs,
        "missing_extraction": missing_extraction,
        "orphan_extractions": orphan_extractions,
        "empty_or_bad_extraction": empty_extractions,
        "incomplete_videos": incomplete_videos,
        "duplicate_video_ids": sorted(set(duplicate_video_ids)),
        "notes": [
            "This report never marks a PDF or video as an approved trading rule.",
            "Source matches remain unreviewed evidence until human review and registry steps complete.",
        ],
    }


def write_ingestion_health_report(
    output_path: Path | str = DEFAULT_REPORT_PATH,
    **kwargs,
) -> dict:
    report = assess_ingestion_health(**kwargs)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["output_path"] = str(path)
    return report


__all__ = [
    "assess_ingestion_health",
    "write_ingestion_health_report",
    "DEFAULT_REPORT_PATH",
]
