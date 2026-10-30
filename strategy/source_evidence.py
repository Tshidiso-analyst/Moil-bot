from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable


SOURCE_QUERIES = (
    "liquidity and liquidity sweeps",
    "market structure higher highs higher lows",
    "fair value gap entry conditions",
    "order blocks and market structure",
    "higher timeframe bias and alignment",
    "trading sessions and kill zones",
    "stop loss invalidation and take profit",
    "risk management position sizing",
    "risk reward and trade management",
    "fundamental news economic events",
    "strategy entry and exit rules",
)

DEFAULT_OUTPUT = Path(
    "knowledge/reports/strategy_source_evidence.json"
)


def collect_source_evidence(
    search_fn: Callable | None = None,
    queries=SOURCE_QUERIES,
    limit: int = 8,
) -> dict:
    """
    Collect actual PDF/video search passages with provenance.

    These are unreviewed evidence records, not approved trading rules.
    Nothing in this module generates or submits trades.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer.")

    if search_fn is None:
        from knowledge.unified_search import search_all_knowledge
        search_fn = search_all_knowledge

    records_by_key = {}
    errors = []

    for query in queries:
        try:
            results = search_fn(query, limit=limit) or []
        except Exception as exc:
            errors.append({
                "query": query,
                "error_type": type(exc).__name__,
                "message": str(exc)[:300],
            })
            continue

        for item in results:
            if not isinstance(item, dict):
                continue

            source_type = str(
                item.get("source_type") or item.get("type") or ""
            ).strip().lower()

            if source_type not in {"pdf", "video"}:
                continue

            title = str(item.get("title") or item.get("source") or "").strip()
            snippet = str(item.get("snippet") or item.get("text") or "").strip()
            url = str(item.get("url") or "").strip()
            video_id = str(item.get("video_id") or "").strip()
            page = item.get("page")

            if source_type == "pdf":
                locator = f"page {page}" if page is not None else "page unknown"
            else:
                locator = (
                    f"video ID {video_id}"
                    if video_id
                    else (url or "video ID unknown")
                )

            # Keep a specific passage separate from other passages in the
            # same source. Hash only real result fields; never invent IDs.
            identity = json.dumps(
                [
                    source_type,
                    title,
                    locator,
                    " ".join(snippet.split()),
                    url,
                ],
                ensure_ascii=False,
            )
            evidence_id = sha256(identity.encode("utf-8")).hexdigest()[:20]
            key = evidence_id

            try:
                score = float(item.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0

            if key not in records_by_key:
                records_by_key[key] = {
                    "evidence_id": evidence_id,
                    "source_type": source_type,
                    "title": title or "Untitled source",
                    "locator": locator,
                    "page": page if source_type == "pdf" else None,
                    "video_id": video_id if source_type == "video" else None,
                    "url": url,
                    "snippet": snippet[:2000],
                    "search_score": score,
                    "matched_queries": [],
                    "review_status": "unreviewed",
                    "rule_status": "not_yet_extracted_or_validated",
                }

            matched = records_by_key[key]["matched_queries"]
            if query not in matched:
                matched.append(query)

    records = sorted(
        records_by_key.values(),
        key=lambda record: (
            record["source_type"],
            record["title"].casefold(),
            str(record["locator"]),
        ),
    )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "queries": list(queries),
        "record_count": len(records),
        "source_counts": dict(Counter(
            record["source_type"] for record in records
        )),
        "errors": errors,
        "records": records,
    }


def write_source_evidence(
    output_path: str | Path = DEFAULT_OUTPUT,
    search_fn: Callable | None = None,
    queries=SOURCE_QUERIES,
    limit: int = 8,
) -> dict:
    report = collect_source_evidence(
        search_fn=search_fn,
        queries=queries,
        limit=limit,
    )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    report["output_path"] = str(path)
    return report


def main() -> None:
    report = write_source_evidence()

    print("===== STRATEGY SOURCE EVIDENCE =====")
    print("Output:", report["output_path"])
    print("Unique passages:", report["record_count"])
    print("Source counts:", report["source_counts"])
    print("Search errors:", len(report["errors"]))
    print(
        "Review status: unreviewed evidence; "
        "no trading rules have been approved by this process."
    )


if __name__ == "__main__":
    main()
