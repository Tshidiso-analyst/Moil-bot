"""Search saved YouTube transcripts and local PDF knowledge together."""

import json
import re
from pathlib import Path

import pymupdf

from knowledge.search import DEFAULT_KNOWLEDGE_PATH

KNOWLEDGE_ROOT = Path(__file__).resolve().parent
DEFAULT_PDF_DIRECTORY = KNOWLEDGE_ROOT / "documents"
DEFAULT_EXTRACTED_DIRECTORY = KNOWLEDGE_ROOT / "extracted"
DEFAULT_CATALOG_PATH = KNOWLEDGE_ROOT / "sources" / "pdf_catalog.json"

_PAGE_MARKER = re.compile(r"(?m)^--- Page (\d+) ---[ \t]*$")
_CACHE = {}


def _terms(query: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"[a-z0-9]+", query.lower())))


def _snippet(text: str, terms: list[str], max_length: int = 360) -> str:
    if not text:
        return ""

    lowered = text.lower()
    positions = [
        lowered.find(term)
        for term in terms
        if lowered.find(term) >= 0
    ]
    start_at = min(positions) if positions else 0
    start = max(0, start_at - 100)
    end = min(len(text), start + max_length)
    excerpt = text[start:end].strip()

    if start:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt += "..."
    return excerpt


def _score(
    query: str,
    terms: list[str],
    title: str,
    text: str,
    concepts: list[str],
) -> int:
    title_lower = title.lower()
    text_lower = text.lower()
    concept_values = [item.lower().strip() for item in concepts]
    concept_text = " ".join(concept_values)

    phrase_pattern = re.compile(
        r"\b" + r"\s+".join(re.escape(term) for term in terms) + r"\b"
    )

    score = 0

    if query in concept_values:
        score += 50
    elif query in concept_text:
        score += 30

    if phrase_pattern.search(title_lower):
        score += 35
    if phrase_pattern.search(text_lower):
        score += 20

    title_terms = set(_terms(title_lower))
    text_terms = set(_terms(text_lower))
    concept_terms = set(_terms(concept_text))

    if all(term in title_terms for term in terms):
        score += 12
    if all(term in concept_terms for term in terms):
        score += 12
    if all(term in text_terms for term in terms):
        score += 8

    for term in terms:
        if term in title_terms:
            score += 3
        if term in concept_terms:
            score += 2
        if term in text_terms:
            score += 1

    return score


def _load_video_records(knowledge_path: Path) -> list[dict]:
    if not knowledge_path.exists():
        return []

    with knowledge_path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)

    records = data.get("records", []) if isinstance(data, dict) else []
    if not isinstance(records, list):
        return []

    return [record for record in records if isinstance(record, dict)]


def _catalog_titles() -> dict[str, str]:
    if not DEFAULT_CATALOG_PATH.exists():
        return {}

    try:
        with DEFAULT_CATALOG_PATH.open("r", encoding="utf-8-sig") as file:
            catalogue = json.load(file)
    except (OSError, ValueError):
        return {}

    if not isinstance(catalogue, list):
        return {}

    return {
        str(item["file"]).lower(): str(item["title"])
        for item in catalogue
        if isinstance(item, dict) and item.get("file") and item.get("title")
    }


def _cache_key(paths: list[Path]) -> tuple:
    details = []
    for path in paths:
        try:
            stat = path.stat()
            details.append((str(path.resolve()), stat.st_mtime_ns, stat.st_size))
        except OSError:
            details.append((str(path.resolve()), None, None))
    return tuple(details)


def _load_extracted_pages(
    extracted_directory: Path,
    pdf_directory: Path,
) -> list[dict]:
    if not extracted_directory.exists():
        return []

    text_files = sorted(extracted_directory.glob("*.txt"))
    text_files = [path for path in text_files if path.name != "__init__.py"]
    if not text_files:
        return []

    catalogue = _catalog_titles()
    tracked_paths = text_files + [
        DEFAULT_CATALOG_PATH,
        extracted_directory,
    ]
    key = ("extracted",) + _cache_key(tracked_paths)

    if key in _CACHE:
        return _CACHE[key]

    records = []

    for text_path in text_files:
        try:
            content = text_path.read_text(encoding="utf-8-sig")
        except OSError:
            continue

        markers = list(_PAGE_MARKER.finditer(content))
        if not markers:
            continue

        pdf_name = text_path.stem + ".pdf"
        pdf_path = pdf_directory / pdf_name
        title = catalogue.get(pdf_name.lower(), text_path.stem.replace("_", " ").replace("-", " ").replace("-", " "))

        for index, marker in enumerate(markers):
            start = marker.end()
            end = markers[index + 1].start() if index + 1 < len(markers) else len(content)
            page_text = content[start:end].strip()

            if not page_text:
                continue

            records.append({
                "title": title,
                "text": page_text,
                "source_type": "pdf",
                "location": str(pdf_path),
                "page": int(marker.group(1)),
                "url": None,
                "video_id": None,
            })

    _CACHE.clear()
    _CACHE[key] = records
    return records


def _read_pdf_pages(pdf_directory: Path) -> list[dict]:
    if not pdf_directory.exists():
        return []

    pdf_files = sorted(
        path for path in pdf_directory.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )
    key = ("pdf",) + _cache_key(pdf_files)

    if key in _CACHE:
        return _CACHE[key]

    records = []

    for pdf_path in pdf_files:
        try:
            with pymupdf.open(pdf_path) as document:
                for page_number, page in enumerate(document, start=1):
                    text = page.get_text("text").strip()
                    if not text:
                        continue

                    records.append({
                        "title": pdf_path.stem.replace("_", " ").replace("-", " ").replace("-", " "),
                        "text": text,
                        "source_type": "pdf",
                        "location": str(pdf_path),
                        "page": page_number,
                        "url": None,
                        "video_id": None,
                    })
        except (OSError, RuntimeError, ValueError):
            # Skip damaged or password-protected files without stopping search.
            continue

    _CACHE.clear()
    _CACHE[key] = records
    return records


def _pdf_page_records(
    pdf_directory: Path,
    use_extracted_text: bool = False,
) -> list[dict]:
    if use_extracted_text:
        extracted = _load_extracted_pages(
            DEFAULT_EXTRACTED_DIRECTORY,
            pdf_directory,
        )
        if extracted:
            return extracted

    return _read_pdf_pages(pdf_directory)


def search_all_knowledge(
    query: str,
    limit: int = 10,
    video_knowledge_path: str | Path | None = None,
    pdf_directory: str | Path | None = None,
) -> list[dict]:
    """Search saved video records and PDF pages in one ranked result list.

    The default PDF library uses previously extracted, page-marked text when
    available. Custom PDF directories are read directly. Results identify
    the source type and include a page number for PDF matches.
    """
    if not isinstance(query, str) or not query.strip():
        return []

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    terms = _terms(query)
    if not terms:
        return []

    normalized_query = " ".join(terms)
    knowledge_path = (
        Path(video_knowledge_path)
        if video_knowledge_path is not None
        else DEFAULT_KNOWLEDGE_PATH
    )
    use_extracted_text = pdf_directory is None
    pdf_root = (
        Path(pdf_directory)
        if pdf_directory is not None
        else DEFAULT_PDF_DIRECTORY
    )

    candidates = []

    for record in _load_video_records(knowledge_path):
        title = str(record.get("title") or "Untitled video")
        text = str(record.get("text") or "")
        raw_concepts = record.get("concepts", [])

        if not isinstance(raw_concepts, list):
            raw_concepts = []

        concepts = []
        for concept in raw_concepts:
            if concept is not None:
                concepts.extend(
                    part.strip()
                    for part in str(concept).split(",")
                    if part.strip()
                )

        concepts = list(dict.fromkeys(concepts))
        score = _score(normalized_query, terms, title, text, concepts)

        if score <= 0:
            continue

        candidates.append({
            "title": title,
            "source_type": "video",
            "location": record.get("url") or record.get("video_id") or "",
            "url": record.get("url"),
            "video_id": record.get("video_id"),
            "page": None,
            "concepts": concepts,
            "snippet": _snippet(text, terms),
            "score": score,
        })

    for record in _pdf_page_records(pdf_root, use_extracted_text):
        title = record["title"]
        text = record["text"]
        score = _score(normalized_query, terms, title, text, [])

        if score <= 0:
            continue

        candidates.append({
            "title": title,
            "source_type": "pdf",
            "location": record["location"],
            "url": None,
            "video_id": None,
            "page": record["page"],
            "concepts": [],
            "snippet": _snippet(text, terms),
            "score": score,
        })

    candidates.sort(
        key=lambda item: (
            -item["score"],
            item["source_type"],
            item["title"].lower(),
            item["page"] or 0,
        )
    )

    # Diversify results when more than one source is relevant.
    source_titles = {
        (item["source_type"], item["title"])
        for item in candidates
    }

    if len(source_titles) <= 1:
        return candidates[:limit]

    selected = []
    deferred = []
    pdf_counts = {}

    for item in candidates:
        if item["source_type"] == "pdf":
            title = item["title"]
            if pdf_counts.get(title, 0) >= 2:
                deferred.append(item)
                continue
            pdf_counts[title] = pdf_counts.get(title, 0) + 1

        selected.append(item)

        if len(selected) >= limit:
            return selected[:limit]

    # Use deferred pages only when other sources did not fill the limit.
    for item in deferred:
        if len(selected) >= limit:
            break
        selected.append(item)

    return selected[:limit]
