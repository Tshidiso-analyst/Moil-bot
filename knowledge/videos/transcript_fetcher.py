from __future__ import annotations

import argparse
import json
import shutil
import time
from collections import Counter
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

CATALOG = Path("knowledge/videos/innercircletrader_catalog.json")
REPORT = Path("knowledge/videos/transcript_fetch_report.json")
DEFAULT_LANGUAGES = ("en", "en-US")


def load_catalog():
    data = json.loads(CATALOG.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return data, data, None
    if isinstance(data, dict):
        for key in ("videos", "items", "results", "entries"):
            if isinstance(data.get(key), list):
                return data, data[key], key
    raise ValueError("Unsupported catalogue structure; no changes made.")


def save_catalog(data, videos, list_key):
    if list_key is None:
        output = videos
    else:
        data[list_key] = videos
        if "video_count" in data:
            data["video_count"] = len(videos)
        output = data

    temporary = CATALOG.with_suffix(CATALOG.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(output, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(CATALOG)
    finally:
        if temporary.exists():
            temporary.unlink()


def is_ip_block(message: str, exception_name: str) -> bool:
    lowered = f"{exception_name} {message}".lower()
    return any(
        marker in lowered
        for marker in (
            "ipblocked",
            "blocking requests from your ip",
            "toomanyrequests",
            "too many requests",
            "requestblocked",
        )
    )


def is_disabled(message: str, exception_name: str) -> bool:
    lowered = f"{exception_name} {message}".lower()
    return any(
        marker in lowered
        for marker in ("transcriptsdisabled", "subtitles are disabled")
    )


def fetch_one(api, video: dict, languages: list[str]) -> str:
    transcript = api.fetch(video["video_id"], languages=languages)
    entries = transcript.to_raw_data()
    text = "\n".join(
        str(entry.get("text", "")).strip()
        for entry in entries
        if str(entry.get("text", "")).strip()
    )
    if not text:
        raise ValueError("Empty transcript returned.")

    video["transcript"] = text
    video["transcript_language"] = getattr(transcript, "language_code", None) or "unknown"
    video["transcript_language_name"] = getattr(transcript, "language", None) or "unknown"
    video["transcript_is_generated"] = bool(getattr(transcript, "is_generated", False))
    video["transcript_segments"] = len(entries)
    video["transcript_status"] = "downloaded"
    video["learning_status"] = "transcript_available"
    video.pop("transcript_error", None)
    return text


def main():
    parser = argparse.ArgumentParser(
        description="Download all available Inner Circle Trader channel transcripts."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of videos to attempt. Default: all eligible videos.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=10.0,
        help="Seconds between transcript requests (default: 10 for safer bulk ingestion).",
    )
    parser.add_argument(
        "--languages",
        default="en,en-US",
        help="Comma-separated preferred caption languages (default: en,en-US).",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Retry videos previously marked unavailable_or_error.",
    )
    parser.add_argument(
        "--retry-ip-blocked",
        action="store_true",
        help="Retry prior IP-blocked entries. Use only after the network/IP situation changes.",
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.delay < 0:
        parser.error("--delay cannot be negative")
    languages = [part.strip() for part in args.languages.split(",") if part.strip()]
    if not languages:
        parser.error("--languages must contain at least one language code")
    if not CATALOG.exists():
        raise SystemExit(f"Catalogue not found: {CATALOG}. Run the full catalogue sync first.")

    data, videos, list_key = load_catalog()
    backup = CATALOG.with_suffix(".json.before-full-fetch")
    if not backup.exists():
        shutil.copy2(CATALOG, backup)
    print(f"Catalogue backup: {backup}")
    print(f"Catalogue entries: {len(videos)}")
    print(f"Preferred languages: {', '.join(languages)}")
    print("Attempt limit: all eligible videos" if args.limit is None else f"Attempt limit: {args.limit}")

    api = YouTubeTranscriptApi()
    attempted = downloaded = disabled = failed = skipped = 0
    blocked = False
    failures = Counter()
    started = time.time()

    for index, video in enumerate(videos, start=1):
        if not isinstance(video, dict):
            skipped += 1
            continue
        if args.limit is not None and attempted >= args.limit:
            break

        video_id = str(video.get("video_id") or "").strip()
        if not video_id:
            video["transcript_status"] = "invalid_video_id"
            skipped += 1
            continue

        existing_text = video.get("transcript")
        if isinstance(existing_text, str) and existing_text.strip():
            video["transcript_status"] = "downloaded"
            video.setdefault("learning_status", "transcript_available")
            skipped += 1
            continue

        status = video.get("transcript_status", "not_checked")
        eligible = status in ("not_checked", "not_attempted", None, "")
        if status == "unavailable_or_error" and args.retry_errors:
            eligible = True
        if status == "ip_blocked" and args.retry_ip_blocked:
            eligible = True
        if not eligible:
            skipped += 1
            continue

        attempted += 1
        title = video.get("title") or video_id
        print(f"[{index}/{len(videos)}] {title} ({video_id})")
        try:
            text = fetch_one(api, video, languages)
            downloaded += 1
            print(f"  Downloaded {len(text):,} characters; language={video['transcript_language']}; generated={video['transcript_is_generated']}")
        except Exception as exc:
            message = str(exc).replace("\n", " ")[:500]
            name = type(exc).__name__
            video["transcript_error"] = message
            if is_ip_block(message, name):
                video["transcript_status"] = "ip_blocked"
                blocked = True
                failures["ip_blocked"] += 1
                print("  YouTube rate/IP block detected; progress saved and ingestion stopped.")
            elif is_disabled(message, name):
                video["transcript_status"] = "transcript_disabled"
                disabled += 1
                failures["transcript_disabled"] += 1
                print("  Captions disabled.")
            else:
                video["transcript_status"] = "unavailable_or_error"
                failed += 1
                failures[name or "unknown_error"] += 1
                print(f"  Transcript unavailable: {name}: {message[:180]}")

        # Durable checkpoint after every attempt, including failures.
        save_catalog(data, videos, list_key)
        if blocked:
            break
        if args.delay and attempted < (args.limit or len(videos)):
            time.sleep(args.delay)

    save_catalog(data, videos, list_key)
    statuses = Counter(
        str(v.get("transcript_status", "not_checked"))
        for v in videos if isinstance(v, dict)
    )
    report = {
        "channel": "@InnerCircleTrader",
        "catalogue_count": len(videos),
        "attempted_this_run": attempted,
        "downloaded_this_run": downloaded,
        "disabled_this_run": disabled,
        "failed_this_run": failed,
        "skipped_this_run": skipped,
        "stopped_for_ip_block": blocked,
        "status_counts": dict(statuses),
        "failures_by_type": dict(failures),
        "elapsed_seconds": round(time.time() - started, 2),
        "catalogue": str(CATALOG),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n===== FULL CHANNEL TRANSCRIPT REPORT =====")
    print(f"Catalogue videos: {len(videos)}")
    print(f"Attempted: {attempted}; downloaded: {downloaded}; disabled: {disabled}; errors: {failed}")
    print(f"Remaining/unattempted: {sum(count for status, count in statuses.items() if status in ('not_checked', 'not_attempted', 'unavailable_or_error', 'ip_blocked'))}")
    print(f"Stopped by IP block: {blocked}")
    print(f"Status counts: {dict(statuses)}")
    print(f"Report: {REPORT}")


if __name__ == "__main__":
    main()
