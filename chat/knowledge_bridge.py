from __future__ import annotations

from typing import Any, Callable

from chat.service import ChatMessage, chat_service


def format_evidence_citations(results: list[dict], query: str, limit: int = 5) -> str:
    """Format search passages with explicit source citations."""
    lines = [f"**Knowledge search · {query.strip()}**"]
    if not results:
        lines.append("No matching PDF or video passages found.")
        lines.append("No trading rule was created from this search.")
        return "\n".join(lines)

    for index, item in enumerate(results[:limit], start=1):
        source_type = str(item.get("source_type") or item.get("type") or "source").lower()
        title = str(item.get("title") or "Untitled").strip()
        snippet = " ".join(str(item.get("snippet") or item.get("text") or "").split())
        if len(snippet) > 220:
            snippet = snippet[:217].rstrip() + "..."

        if source_type == "pdf":
            page = item.get("page")
            locator = f"page {page}" if page is not None else "page unknown"
            citation = f"[{index}] PDF · {title} · {locator}"
        elif source_type == "video":
            video_id = str(item.get("video_id") or "").strip()
            url = str(item.get("url") or "").strip()
            locator = video_id or url or "video id unknown"
            citation = f"[{index}] Video · {title} · {locator}"
        else:
            citation = f"[{index}] {source_type} · {title}"

        lines.append(citation)
        if snippet:
            lines.append(f"    {snippet}")

    lines.append("These passages are unreviewed evidence only — not approved rules.")
    return "\n".join(lines)


def post_knowledge_search(
    query: str,
    *,
    search_fn: Callable[..., list[dict]] | None = None,
    limit: int = 5,
    room: str = "analysis",
    author: str = "Moil Knowledge",
) -> ChatMessage:
    """Search PDF/video knowledge and post cited results into chat."""
    if search_fn is None:
        from knowledge.unified_search import search_all_knowledge

        search_fn = search_all_knowledge

    results = search_fn(query, limit=limit) or []
    message = format_evidence_citations(results, query=query, limit=limit)
    return chat_service.post_message(author=author, message=message, room=room)


def format_ingestion_health(report: dict[str, Any]) -> str:
    counts = report.get("counts") or {}
    status = str(report.get("status") or "unknown")
    lines = [
        f"**Knowledge ingestion health · {status}**",
        (
            f"PDFs: {counts.get('pdf_files', 0)} · "
            f"Extracted: {counts.get('extracted_files', 0)} · "
            f"Videos: {counts.get('video_records', 0)}"
        ),
    ]

    problems = []
    for key, label in (
        ("missing_from_disk", "Missing PDF files"),
        ("missing_extraction", "PDFs without extraction"),
        ("empty_or_bad_extraction", "Empty/bad extractions"),
        ("incomplete_videos", "Incomplete videos"),
        ("duplicate_video_ids", "Duplicate video IDs"),
        ("catalog_errors", "Catalogue errors"),
        ("video_errors", "Video catalogue errors"),
    ):
        items = report.get(key) or []
        if items:
            problems.append(f"{label}: {len(items)}")

    if problems:
        lines.append("Issues: " + "; ".join(problems))
    else:
        lines.append("No structural ingestion issues detected.")

    lines.append("Nothing in this report approves or enables a trading rule.")
    return "\n".join(lines)


def post_ingestion_health(
    report: dict[str, Any] | None = None,
    *,
    room: str = "analysis",
    author: str = "Moil Knowledge",
) -> ChatMessage:
    if report is None:
        from knowledge.ingestion_health import assess_ingestion_health

        report = assess_ingestion_health()
    message = format_ingestion_health(report)
    return chat_service.post_message(author=author, message=message, room=room)


__all__ = [
    "format_evidence_citations",
    "post_knowledge_search",
    "format_ingestion_health",
    "post_ingestion_health",
]
