from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

CATALOG = Path("knowledge/videos/innercircletrader_catalog.json")


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


def main():
    parser = argparse.ArgumentParser(
        description="Fetch YouTube transcripts safely into the catalogue."
    )
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Retry ordinary unavailable/error entries, but never disabled or IP-blocked entries.",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.delay < 0:
        parser.error("--delay cannot be negative")
    if not CATALOG.exists():
        raise SystemExit(f"Catalogue not found: {CATALOG}")

    data, videos, list_key = load_catalog()

    backup = CATALOG.with_suffix(".json.before-safe-fetch")
    if not backup.exists():
        shutil.copy2(CATALOG, backup)
    print(f"Catalogue backup: {backup}")

    api = YouTubeTranscriptApi()
    attempted = 0
    successful = 0
    blocked = False
    disabled = 0
    failed = 0

    for video in videos:
        if attempted >= args.limit:
            break
        if not isinstance(video, dict):
            continue

        if str(video.get("transcript", "")).strip():
            video["transcript_status"] = "downloaded"
            continue

        status = video.get("transcript_status", "not_checked")

        # Never retry known disabled subtitles or an IP block automatically.
        if status in ("transcript_disabled", "ip_blocked"):
            continue

        if status not in ("not_checked", "not_attempted", None, ""):
            if not (args.retry_errors and status == "unavailable_or_error"):
                continue

        video_id = video.get("video_id")
        if not video_id:
            continue

        attempted += 1
        title = video.get("title") or video_id
        print(f"\n[{attempted}/{args.limit}] {title}")

        try:
            transcript = api.fetch(video_id, languages=["en"])
            entries = transcript.to_raw_data()
            transcript_text = "\n".join(
                str(entry.get("text", "")).strip()
                for entry in entries
                if str(entry.get("text", "")).strip()
            )

            if not transcript_text:
                video["transcript_status"] = "unavailable_or_error"
                video["transcript_error"] = "Empty transcript returned."
                failed += 1
                print("No transcript text returned.")
            else:
                video["transcript"] = transcript_text
                video["transcript_language"] = "en"
                video["transcript_segments"] = len(entries)
                video["transcript_status"] = "downloaded"
                video["learning_status"] = "transcript_available"
                video.pop("transcript_error", None)
                successful += 1
                print(f"Downloaded {len(transcript_text)} characters.")

        except Exception as exc:
            message = str(exc)
            lowered = (type(exc).__name__ + " " + message).lower()
            video["transcript_error"] = message[:500]

            if "transcriptsdisabled" in lowered or "subtitles are disabled" in lowered:
                video["transcript_status"] = "transcript_disabled"
                disabled += 1
                print("Subtitles are disabled for this video.")
            elif (
                "ipblocked" in lowered
                or "blocking requests from your ip" in lowered
                or "toomanyrequests" in lowered
                or "too many requests" in lowered
            ):
                video["transcript_status"] = "ip_blocked"
                blocked = True
                print("YouTube is blocking requests. Saving progress and stopping.")
            else:
                video["transcript_status"] = "unavailable_or_error"
                failed += 1
                print(f"Transcript unavailable: {message[:200]}")

        # Save the original root structure and all progress after each attempt.
        save_catalog(data, videos, list_key)

        if blocked:
            break

        if attempted < args.limit and args.delay > 0:
            time.sleep(args.delay)

    save_catalog(data, videos, list_key)

    print("\n===== TRANSCRIPT FETCH SUMMARY =====")
    print("Videos attempted:", attempted)
    print("Transcripts downloaded:", successful)
    print("Subtitles disabled:", disabled)
    print("Other errors:", failed)
    print("Stopped due to IP blocking:", blocked)
    print("Catalogue videos:", len(videos))
    print("Catalogue saved:", CATALOG)


if __name__ == "__main__":
    main()
