from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi


CATALOG = Path("knowledge/videos/innercircletrader_catalog.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    if not CATALOG.exists():
        raise SystemExit(f"Catalogue not found: {CATALOG}")

    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    videos = data.get("videos", [])
    api = YouTubeTranscriptApi()

    attempted = 0
    successful = 0

    for video in videos:
        if attempted >= args.limit:
            break

        if video.get("transcript_status") == "downloaded":
            continue

        video_id = video.get("video_id")
        if not video_id:
            continue

        attempted += 1
        print(f"\n[{attempted}/{args.limit}] {video.get('title', video_id)}")

        try:
            transcript = api.fetch(video_id, languages=["en"])
            entries = transcript.to_raw_data()
            text = "\n".join(
                str(entry.get("text", "")).strip()
                for entry in entries
                if str(entry.get("text", "")).strip()
            )

            if not text:
                video["transcript_status"] = "empty_transcript"
                print("No transcript text returned.")
            else:
                video["transcript"] = text
                video["transcript_language"] = "en"
                video["transcript_segments"] = len(entries)
                video["transcript_status"] = "downloaded"
                video["learning_status"] = "transcript_available"
                successful += 1
                print(f"Transcript retrieved: {len(text)} characters.")

        except Exception as exc:
            video["transcript_status"] = "unavailable_or_error"
            video["transcript_error"] = str(exc)[:500]
            print(f"Transcript unavailable: {str(exc)[:250]}")

        time.sleep(max(0, args.delay))

    data["video_count"] = len(videos)
    CATALOG.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n===== TRANSCRIPT TEST SUMMARY =====")
    print("Videos checked:", attempted)
    print("Transcripts retrieved:", successful)
    print("Catalogue saved:", CATALOG)


if __name__ == "__main__":
    main()
