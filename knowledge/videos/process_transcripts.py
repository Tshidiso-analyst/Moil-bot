"""Process available video transcripts through Moil-bot's knowledge engine."""

import json
from pathlib import Path

from knowledge.concepts.extractor import extract_concepts
from knowledge.consolidated.consolidator import consolidate_knowledge

CATALOG_PATH = Path("knowledge/videos/innercircletrader_catalog.json")
OUTPUT_PATH = Path("knowledge/videos/processed_knowledge.json")


def process_transcripts() -> dict:
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"Video catalogue not found: {CATALOG_PATH}")

    catalogue = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    videos = catalogue.get("videos", [])
    records = []
    skipped = 0

    for video in videos:
        transcript = video.get("transcript", "").strip()

        if not transcript:
            skipped += 1
            continue

        video_id = video.get("video_id") or video.get("id")
        if not video_id:
            skipped += 1
            continue

        concepts = extract_concepts(transcript)

        record = consolidate_knowledge(
            source_id=f"youtube-{video_id}",
            title=video.get("title", "Untitled video"),
            text=transcript,
            concepts=concepts,
        )

        # Preserve the original video as the source reference.
        record["source_type"] = "youtube_transcript"
        record["video_id"] = video_id
        record["url"] = video.get(
            "url", f"https://www.youtube.com/watch?v={video_id}"
        )
        record["transcript_language"] = video.get("transcript_language", "unknown")
        record["learning_status"] = "concepts_extracted"
        records.append(record)

    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "source_channel": catalogue.get(
                    "channel_handle", "@InnerCircleTrader"
                ),
                "processed_count": len(records),
                "skipped_without_transcript": skipped,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    concept_counts = {}
    for record in records:
        for concept in record["concepts"]:
            concept_counts[concept] = concept_counts.get(concept, 0) + 1

    print("===== TRANSCRIPT PROCESSING SUMMARY =====")
    print(f"Videos in catalogue: {len(videos)}")
    print(f"Transcripts processed: {len(records)}")
    print(f"Videos skipped (no transcript or ID): {skipped}")
    print(f"Knowledge records saved to: {OUTPUT_PATH}")
    print("Extracted concepts:")
    if concept_counts:
        for concept, count in sorted(concept_counts.items()):
            print(f"  {concept}: {count} video(s)")
    else:
        print("  No known concepts detected.")

    return {
        "processed": len(records),
        "skipped": skipped,
        "concept_counts": concept_counts,
    }


if __name__ == "__main__":
    process_transcripts()
