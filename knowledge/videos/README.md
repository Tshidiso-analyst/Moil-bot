# Full Inner Circle Trader YouTube ingestion

Moil-bot's ICT source library is designed to cover the public upload history of
[Inner Circle Trader](https://www.youtube.com/@InnerCircleTrader/videos), not
only a small manually selected playlist.

## What the workflow does

1. `youtube_catalog.py` resolves the channel's uploads playlist and paginates
   through every available public upload page (50 entries per API request).
2. `transcript_fetcher.py` attempts every eligible catalogue entry by default.
   It saves a checkpoint after each attempt, records the caption language and
   whether captions are auto-generated, and resumes on the next run.
3. `process_transcripts.py --catalogue-only` extracts concepts from transcripts
   already saved in the catalogue and updates `processed_knowledge.json` without
   issuing another round of YouTube requests.
4. Reports record catalogue size, downloaded captions, disabled captions,
   errors and IP/rate blocking. A blocked run stops safely rather than hammering
   YouTube.

Videos with disabled, missing or inaccessible captions remain catalogued with
an explicit status. Moil-bot must not claim to have learned from a video whose
transcript was not obtained. The original title, video ID and URL remain linked
to each processed knowledge record.

## Requirements

- Python dependencies from `requirements.txt` installed.
- A YouTube Data API key with YouTube Data API v3 enabled, set as
  `YOUTUBE_API_KEY` for catalogue discovery.
- Outbound internet access for YouTube API and caption retrieval.

PowerShell:

```powershell
$env:YOUTUBE_API_KEY = "YOUR_YOUTUBE_DATA_API_KEY"
```

Do not commit the API key or place it in source control.

## Run the complete workflow

From the repository root:

```powershell
npm run ingest:ict:youtube
```

Or run the stages separately:

```powershell
python -m knowledge.videos.youtube_catalog
python -m knowledge.videos.transcript_fetcher
python -m knowledge.videos.process_transcripts --catalogue-only
```

The transcript fetcher defaults to all eligible videos with a 10-second delay.
For a small smoke test, pass `--limit 3 --delay 2`. To retry ordinary
transcript errors, pass `--retry-errors`. IP-blocked entries are not retried
unless `--retry-ip-blocked` is explicitly supplied after the network/IP
situation has changed.

If YouTube blocks requests, the script saves its progress and stops. Rerun it
later to continue. Existing downloaded transcripts and statuses are preserved
when the catalogue is refreshed.

## Generated local data

- `knowledge/videos/innercircletrader_catalog.json` — full metadata catalogue,
  transcript text, caption status and language.
- `knowledge/videos/transcript_fetch_report.json` — latest bulk-fetch report.
- `knowledge/videos/processed_knowledge.json` — searchable extracted lessons.
- `knowledge/videos/transcript_processing_report.json` — extraction report.

These data files are generated locally and should not contain API credentials.
Keep large transcript/catalogue artifacts out of Git unless the repository's
data-storage policy explicitly calls for them.

## Important learning and trading boundary

Transcript extraction is source ingestion, not proof that a trading setup is
profitable. Each extracted concept retains its source video. Candidate rules
must go through strategy review, historical backtesting and out-of-sample
validation before they can be considered for approval. This workflow does not
enable live or demo order execution.
