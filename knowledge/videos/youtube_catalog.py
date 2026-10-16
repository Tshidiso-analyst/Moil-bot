from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CHANNEL_HANDLE = "@InnerCircleTrader"
API_BASE = "https://www.googleapis.com/youtube/v3"
DEFAULT_OUTPUT = Path("knowledge/videos/innercircletrader_catalog.json")


class YouTubeCatalogError(RuntimeError):
    """Raised when YouTube catalogue retrieval fails."""


def _api_get(endpoint: str, params: dict) -> dict:
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise YouTubeCatalogError(
            "YOUTUBE_API_KEY is not set. Configure your YouTube Data API key."
        )

    query = urlencode({**params, "key": api_key})
    request = Request(
        f"{API_BASE}/{endpoint}?{query}",
        headers={"Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise YouTubeCatalogError(
            f"YouTube API request failed: {exc}"
        ) from exc

    if "error" in payload:
        message = payload["error"].get("message", "Unknown YouTube API error")
        raise YouTubeCatalogError(message)

    return payload


def get_uploads_playlist(channel_handle: str = CHANNEL_HANDLE) -> str:
    """Resolve a channel handle to its public uploads playlist ID."""
    result = _api_get(
        "channels",
        {
            "part": "contentDetails",
            "forHandle": channel_handle,
        },
    )

    items = result.get("items", [])
    if not items:
        raise YouTubeCatalogError(
            f"No channel was found for handle {channel_handle}."
        )

    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_channel_videos(
    channel_handle: str = CHANNEL_HANDLE,
    max_pages: int | None = None,
) -> list[dict]:
    """
    Retrieve public upload metadata.

    max_pages=None retrieves all pages available to the API.
    This catalogues videos; it does not download video or transcript content.
    """
    playlist_id = get_uploads_playlist(channel_handle)
    videos: list[dict] = []
    page_token = None
    pages_read = 0
    seen_ids: set[str] = set()

    while True:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        result = _api_get("playlistItems", params)
        pages_read += 1

        for item in result.get("items", []):
            snippet = item.get("snippet", {})
            details = item.get("contentDetails", {})
            video_id = details.get("videoId") or snippet.get(
                "resourceId", {}
            ).get("videoId")

            if not video_id or video_id in seen_ids:
                continue
            seen_ids.add(video_id)

            thumbnails = snippet.get("thumbnails", {})
            thumbnail = (
                thumbnails.get("high")
                or thumbnails.get("medium")
                or thumbnails.get("default")
                or {}
            )

            videos.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "published_at": details.get("videoPublishedAt")
                    or snippet.get("publishedAt", ""),
                    "channel": snippet.get("videoOwnerChannelTitle")
                    or snippet.get("channelTitle", channel_handle),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "thumbnail_url": thumbnail.get("url", ""),
                    "transcript_status": "not_checked",
                    "learning_status": "catalogued_only",
                }
            )

        page_token = result.get("nextPageToken")
        if not page_token:
            break
        if max_pages is not None and pages_read >= max_pages:
            break

    return videos


def save_catalog(videos: list[dict], output_path: Path = DEFAULT_OUTPUT) -> Path:
    """Save the catalogue, merging new metadata without losing existing notes."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, dict] = {}
    if output_path.exists():
        try:
            previous = json.loads(output_path.read_text(encoding="utf-8"))
            existing = {
                item["video_id"]: item
                for item in previous.get("videos", [])
                if item.get("video_id")
            }
        except (json.JSONDecodeError, OSError) as exc:
            raise YouTubeCatalogError(
                f"Could not read existing catalogue {output_path}: {exc}"
            ) from exc

    for video in videos:
        video_id = video["video_id"]
        merged = existing.get(video_id, {}).copy()
        merged.update(video)

        # Preserve user notes and any future extracted lesson text.
        old = existing.get(video_id, {})
        for field in ("notes", "transcript", "concepts"):
            if field in old:
                merged[field] = old[field]

        existing[video_id] = merged

    ordered = sorted(
        existing.values(),
        key=lambda item: item.get("published_at", ""),
        reverse=True,
    )

    output_path.write_text(
        json.dumps(
            {
                "channel_handle": CHANNEL_HANDLE,
                "video_count": len(ordered),
                "catalogue_status": "metadata_only",
                "videos": ordered,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    videos = fetch_channel_videos()
    output = save_catalog(videos)
    print(f"Videos catalogued: {len(videos)}")
    print(f"Saved to: {output}")
    print("Status: metadata only; transcripts have not been processed.")


if __name__ == "__main__":
    main()
