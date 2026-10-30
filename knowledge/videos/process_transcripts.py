from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from collections import Counter
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge.concepts.extractor import extract_concepts
from knowledge.consolidated.consolidator import consolidate_knowledge


VIDEOS_DIR = ROOT / "knowledge" / "videos"
DEFAULT_CATALOG = VIDEOS_DIR / "innercircletrader_catalog.json"
DEFAULT_OUTPUT = VIDEOS_DIR / "processed_knowledge.json"

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def load_catalog(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, list):
        videos = data
    elif isinstance(data, dict):
        for key in ("videos", "items", "results", "entries"):
            if isinstance(data.get(key), list):
                videos = data[key]
                break
        else:
            raise ValueError(f"Cannot find video list in JSON. Root keys: {list(data.keys())}")
    else:
        raise ValueError("Catalogue root must be a list or dict.")
    return [v for v in videos if isinstance(v, dict)]


def extract_video_id(video: dict) -> str | None:
    fields = (
        "video_id", "videoId", "youtube_id", "youtubeId",
        "id", "url", "video_url", "youtube_url", "link",
    )
    for field in fields:
        val = video.get(field)
        if not isinstance(val, str):
            continue
        val = val.strip()
        if VIDEO_ID_PATTERN.fullmatch(val):
            return val
        if "youtube.com" in val or "youtu.be" in val:
            try:
                parsed = urlparse(val)
                host = parsed.netloc.lower().split(":")[0]
                if host.endswith("youtu.be"):
                    candidate = parsed.path.strip("/").split("/")[0]
                elif host.endswith("youtube.com"):
                    if parsed.path == "/watch":
                        candidate = parse_qs(parsed.query).get("v", [""])[0]
                    else:
                        parts = parsed.path.strip("/").split("/")
                        candidate = parts[1] if len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v") else ""
                else:
                    continue
                if VIDEO_ID_PATTERN.fullmatch(candidate):
                    return candidate
            except Exception:
                continue
        # Nested ID object
        if field == "id" and isinstance(video.get("id"), dict):
            nested = video["id"].get("videoId")
            if isinstance(nested, str) and VIDEO_ID_PATTERN.fullmatch(nested):
                return nested
    return None


def fetch_transcript(video_id: str) -> tuple[str | None, str | None]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        data = YouTubeTranscriptApi().fetch(video_id)
        text = " ".join(item.text for item in data if getattr(item, "text", ""))
        if text.strip():
            return text.strip(), None
        return None, "empty_transcript"
    except ImportError:
        return None, "dependency_missing: install youtube-transcript-api"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc).replace(chr(10), ' ')[:240]}"



def saved_transcript(video: dict) -> str | None:
    """Return transcript text already stored in a catalogue entry."""
    value = video.get("transcript")

    if isinstance(value, str) and value.strip():
        return value.strip()

    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(getattr(item, "text", None), str):
                parts.append(item.text)
        text = " ".join(part.strip() for part in parts if part.strip())
        if text:
            return text

    return None


def normalize_concepts(result) -> list[str]:
    if isinstance(result, str):
        return [result] if result.strip() else []
    if isinstance(result, dict):
        result = result.get("concepts") or result.get("extracted_concepts") or list(result.keys())
    if not isinstance(result, (list, tuple, set)):
        return []
    concepts = []
    for item in result:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = item.get("name") or item.get("concept")
            if not isinstance(name, str):
                continue
            name = name.strip()
        else:
            continue
        if name:
            concepts.append(name)
    return concepts


def process_catalog(catalog_path: Path, output_path: Path, limit: int | None = None, delay: float = 1.5) -> int:
    videos = load_catalog(catalog_path)
    if limit is not None:
        videos = videos[:limit]

    existing_records = []
    if output_path.exists():
        try:
            existing_data = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Cannot safely read existing knowledge output: {output_path}"
            ) from exc

        if not isinstance(existing_data, dict) or not isinstance(
            existing_data.get("records", []), list
        ):
            raise RuntimeError(
                f"Existing knowledge output has an invalid structure: {output_path}"
            )

        existing_records = existing_data.get("records", [])

    records = []
    failures = Counter()
    concept_videos = Counter()
    processed = 0

    print(f"Catalogue: {catalog_path}")
    print(f"Videos to examine: {len(videos)}")

    for idx, video in enumerate(videos, start=1):
        video_id = extract_video_id(video)
        title = video.get("title") or video.get("name") or video.get("video_title") or f"Video {idx}"

        if not video_id:
            failures["invalid_or_missing_video_id"] += 1
            print(f"[{idx}/{len(videos)}] SKIP: {title} — no valid ID")
            continue

        transcript = saved_transcript(video)
        error = None
        transcript_source = "catalogue"

        if not transcript:
            transcript_source = "YouTube"
            if delay > 0:
                time.sleep(delay)
            transcript, error = fetch_transcript(video_id)

        if not transcript:
            reason = error or "unknown_transcript_error"
            failures[reason.split(":", 1)[0]] += 1
            print(f"[{idx}/{len(videos)}] SKIP: {title} — {reason}")
            continue

        try:
            extracted = extract_concepts(transcript)
            concepts = normalize_concepts(extracted)
        except Exception as exc:
            failures[f"concept_extraction:{type(exc).__name__}"] += 1
            print(f"[{idx}/{len(videos)}] ERROR extracting concepts for {title}: {exc}")
            continue

        record = consolidate_knowledge(
            source_id=f"youtube-{video_id}",
            title=title,
            text=transcript,
            concepts=concepts,
        )
        record["source_type"] = "youtube_transcript"
        record["video_id"] = video_id
        record["url"] = f"https://www.youtube.com/watch?v={video_id}"
        record["transcript_language"] = video.get("transcript_language", "unknown")
        record["learning_status"] = "concepts_extracted"
        records.append(record)

        processed += 1
        for c in set(concepts):
            concept_videos[c] += 1

        print(
            f"[{idx}/{len(videos)}] OK: {title} "
            f"({len(transcript.split())} words, {len(concepts)} concepts; "
            f"source: {transcript_source})"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    merged_by_id = {}
    records_without_id = []

    for record in existing_records:
        video_key = str(record.get("video_id") or "").strip()
        if video_key:
            merged_by_id[video_key] = record
        else:
            records_without_id.append(record)

    for record in records:
        video_key = str(record.get("video_id") or "").strip()
        if video_key:
            merged_by_id[video_key] = record
        else:
            records_without_id.append(record)

    final_records = records_without_id + list(merged_by_id.values())

    output_data = {
        "source_channel": "@InnerCircleTrader",
        "processed_count": len(final_records),
        "skipped_without_transcript": len(videos) - processed,
        "records": final_records,
    }
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    temp_path.replace(output_path)

    report_path = output_path.with_name("transcript_processing_report.json")
    report = {
        "catalogue": str(catalog_path),
        "catalogue_count": len(videos),
        "transcripts_processed": processed,
        "failures_by_reason": dict(failures),
        "knowledge_records_saved": len(final_records),
        "output": str(output_path),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== TRANSCRIPT PROCESSING SUMMARY =====")
    print(f"Videos examined: {len(videos)}")
    print(f"Transcripts processed: {processed}")
    print(f"Videos skipped: {len(videos) - processed}")
    print(f"Knowledge records saved to: {output_path}")
    print(f"Failure report saved to: {report_path}")

    if failures:
        print("\nFailure reasons:")
        for reason, count in failures.most_common():
            print(f"  {reason}: {count}")

    if concept_videos:
        print("\nExtracted concepts:")
        for concept, count in concept_videos.most_common():
            print(f"  {concept}: {count} video(s)")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch YouTube transcripts and extract trading concepts."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help="Path to the JSON video catalogue.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path for processed knowledge JSON.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N catalogue entries for testing.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds to wait before each online transcript request (default: 1.5).",
    )
    args = parser.parse_args()

    if args.delay < 0:
        parser.error("--delay cannot be negative")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if not args.catalog.is_file():
        parser.error(f"Catalogue file not found: {args.catalog}")

    return process_catalog(args.catalog, args.output, args.limit, args.delay)


if __name__ == "__main__":
    raise SystemExit(main())
