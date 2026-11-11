import json

from knowledge.videos import transcript_fetcher, youtube_catalog


def test_catalog_sync_preserves_downloaded_transcript_and_status(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps({
            "channel_handle": "@InnerCircleTrader",
            "videos": [{
                "video_id": "abcdefghijk",
                "title": "Old title",
                "transcript": "Existing ICT lesson",
                "transcript_status": "downloaded",
                "transcript_language": "en",
                "learning_status": "concepts_extracted",
                "notes": "reviewed",
            }],
        }),
        encoding="utf-8",
    )

    youtube_catalog.save_catalog(
        [{"video_id": "abcdefghijk", "title": "Updated title", "transcript_status": "not_checked",
          "learning_status": "catalogued_only"}],
        path,
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    video = saved["videos"][0]
    assert video["title"] == "Updated title"
    assert video["transcript"] == "Existing ICT lesson"
    assert video["transcript_status"] == "downloaded"
    assert video["transcript_language"] == "en"
    assert video["learning_status"] == "concepts_extracted"
    assert video["notes"] == "reviewed"


def test_catalog_fetch_paginates_until_all_upload_pages(monkeypatch):
    calls = []

    def fake_api_get(endpoint, params):
        calls.append((endpoint, params.copy()))
        if endpoint == "channels":
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "uploads123"}}}]}
        if not params.get("pageToken"):
            return {
                "items": [{
                    "snippet": {"title": "Video 1", "resourceId": {"videoId": "abcdefghijk"}},
                    "contentDetails": {"videoId": "abcdefghijk"},
                }],
                "nextPageToken": "page-2",
            }
        return {
            "items": [{
                "snippet": {"title": "Video 2", "resourceId": {"videoId": "lmnopqrstuv"}},
                "contentDetails": {"videoId": "lmnopqrstuv"},
            }]
        }

    monkeypatch.setattr(youtube_catalog, "_api_get", fake_api_get)
    videos = youtube_catalog.fetch_channel_videos()

    assert [video["video_id"] for video in videos] == ["abcdefghijk", "lmnopqrstuv"]
    assert len([call for call in calls if call[0] == "playlistItems"]) == 2


def test_transcript_error_classification():
    assert transcript_fetcher.is_ip_block("Your IP is blocked", "RequestBlocked")
    assert transcript_fetcher.is_ip_block("Too many requests", "Exception")
    assert transcript_fetcher.is_disabled("Subtitles are disabled", "Exception")
    assert not transcript_fetcher.is_ip_block("Video unavailable", "Exception")


def test_fetch_one_records_language_and_generated_caption_metadata():
    class FakeTranscript:
        language_code = "en"
        language = "English"
        is_generated = True

        def to_raw_data(self):
            return [{"text": "Liquidity sweep"}, {"text": "market structure"}]

    class FakeTrack:
        language_code = "en"
        language = "English"
        is_generated = True

        def fetch(self):
            return FakeTranscript()

    class FakeTrackList:
        def find_transcript(self, languages):
            assert languages == ["en"]
            return FakeTrack()

        def __iter__(self):
            return iter([FakeTrack()])

    class FakeApi:
        def list(self, video_id):
            assert video_id == "abcdefghijk"
            return FakeTrackList()

    video = {"video_id": "abcdefghijk"}
    text = transcript_fetcher.fetch_one(FakeApi(), video, ["en"])

    assert text == "Liquidity sweep\nmarket structure"
    assert video["transcript_status"] == "downloaded"
    assert video["transcript_language"] == "en"
    assert video["transcript_is_generated"] is True
    assert video["transcript_segments"] == 2
