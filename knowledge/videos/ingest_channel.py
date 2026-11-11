from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "knowledge" / "videos" / "innercircletrader_catalog.json"


def run_stage(module: str, *args: str) -> None:
    command = [sys.executable, "-m", module, *args]
    print("\n>>> " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()

    if api_key:
        print("YOUTUBE_API_KEY found: refreshing the complete public channel catalogue.")
        run_stage("knowledge.videos.youtube_catalog")
    elif CATALOG.is_file():
        print(
            "YOUTUBE_API_KEY is not set. Reusing the existing channel catalogue; "
            "no metadata refresh will be performed."
        )
    else:
        print(
            "No YOUTUBE_API_KEY and no existing catalogue. Set YOUTUBE_API_KEY "
            "or restore knowledge/videos/innercircletrader_catalog.json."
        )
        return 2

    print(
        "Starting transcript ingestion for every eligible catalogue entry. "
        "Existing transcripts are retained and skipped."
    )
    run_stage("knowledge.videos.transcript_fetcher", "--retry-errors")
    print("Extracting concepts from every transcript already saved.")
    run_stage("knowledge.videos.process_transcripts", "--catalogue-only")
    print("\nFull-channel ingestion stages completed. Check the JSON reports for "
          "downloaded, disabled, failed, and still-pending videos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
