import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

import pytest

from fundamentals.calendar_feed import (
    CalendarFeedError,
    FmpEconomicCalendarProvider,
    HttpEconomicCalendarProvider,
)


NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def payload(**overrides):
    value = {
        "source": "test-provider",
        "fetched_at": "2026-11-07T11:59:00Z",
        "coverage_start": "2026-11-07T00:00:00Z",
        "coverage_end": "2026-11-14T00:00:00Z",
        "events": [{
            "name": "US CPI",
            "currency": "USD",
            "scheduled_at": "2026-11-10T13:30:00Z",
            "impact": "high",
            "actual": None,
            "forecast": 3.1,
            "previous": 3.0,
            "surprise_bias": "context_dependent",
            "source_url": "https://provider.example/cpi",
        }],
    }
    value.update(overrides)
    return value


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.content[:size]


def provider(**kwargs):
    return HttpEconomicCalendarProvider("https://calendar.example/api", **kwargs)


def test_fetch_parses_a_verified_calendar_snapshot():
    body = json.dumps(payload()).encode()
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(body)):
        snapshot = provider().fetch(now=NOW)

    assert snapshot.source == "test-provider"
    assert len(snapshot.events) == 1
    assert snapshot.events[0].currency == "USD"
    assert snapshot.events[0].forecast == 3.1
    assert snapshot.events[0].scheduled_at.tzinfo is not None


def test_stale_feed_is_rejected():
    stale = payload(fetched_at="2026-11-07T11:00:00Z")
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(json.dumps(stale).encode())):
        with pytest.raises(CalendarFeedError, match="stale"):
            provider().fetch(now=NOW)


def test_feed_without_current_coverage_is_rejected():
    uncovered = payload(coverage_end="2026-11-07T11:00:00Z")
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(json.dumps(uncovered).encode())):
        with pytest.raises(CalendarFeedError, match="does not cover"):
            provider().fetch(now=NOW)


def test_feed_must_identify_source_and_coverage():
    missing = payload(source="")
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(json.dumps(missing).encode())):
        with pytest.raises(CalendarFeedError, match="identify its source"):
            provider().fetch(now=NOW)


def test_naive_now_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        provider().fetch(now=datetime(2026, 11, 7, 12, 0))


def test_non_json_response_is_rejected():
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(b"not json")):
        with pytest.raises(CalendarFeedError, match="valid UTF-8 JSON"):
            provider().fetch(now=NOW)


def test_response_size_limit_is_enforced():
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(b"x" * 30)):
        with pytest.raises(CalendarFeedError, match="size limit"):
            provider(max_bytes=20).fetch(now=NOW)


def test_empty_event_list_can_still_be_verified_if_provider_certifies_coverage():
    empty = payload(events=[])
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(json.dumps(empty).encode())):
        snapshot = provider().fetch(now=NOW)

    assert snapshot.events == ()
    assert snapshot.coverage_start <= NOW <= snapshot.coverage_end


def test_plain_http_is_rejected_for_non_local_calendar_hosts():
    with pytest.raises(CalendarFeedError, match="HTTPS"):
        HttpEconomicCalendarProvider("http://calendar.example/api")


def test_localhost_http_is_allowed_for_development():
    assert HttpEconomicCalendarProvider("http://localhost:8080/calendar")


def test_fmp_maps_documented_utc_calendar_fields():
    body = json.dumps([{
        "date": "2026-11-10 13:30:00",
        "country": "US",
        "event": "Consumer Price Index",
        "currency": "USD",
        "previous": 3.0,
        "estimate": 3.1,
        "actual": None,
        "impact": "High",
    }]).encode()
    fmp = FmpEconomicCalendarProvider("test-secret", days_ahead=7)
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(body)) as request:
        snapshot = fmp.fetch(now=NOW)

    assert snapshot.source == "Financial Modeling Prep"
    assert snapshot.events[0].name == "Consumer Price Index"
    assert snapshot.events[0].impact == "high"
    assert snapshot.events[0].forecast == 3.1
    assert snapshot.events[0].scheduled_at == datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)
    query = parse_qs(urlparse(request.call_args.args[0].full_url).query)
    assert query["apikey"] == ["test-secret"]
    assert query["from"] == ["2026-11-07"]
    assert query["to"] == ["2026-11-14"]



def test_fmp_rejects_missing_or_unrecognized_impact():
    fmp = FmpEconomicCalendarProvider("secret")
    body = json.dumps([{
        "date": "2026-11-10 13:30:00",
        "event": "Unclassified event",
        "currency": "USD",
        "impact": "None",
    }]).encode()
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(body)):
        with pytest.raises(CalendarFeedError, match="impact is missing or unrecognized"):
            fmp.fetch(now=NOW)

def test_fmp_rejects_missing_api_key():
    with pytest.raises(CalendarFeedError, match="API key is required"):
        FmpEconomicCalendarProvider(" ")


def test_fmp_rejects_windows_over_documented_90_day_limit():
    with pytest.raises(ValueError, match="between 1 and 90"):
        FmpEconomicCalendarProvider("secret", days_ahead=91)


def test_fmp_rejects_non_array_error_payload():
    fmp = FmpEconomicCalendarProvider("secret")
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(b'{"Error Message":"invalid key"}')):
        with pytest.raises(CalendarFeedError, match="JSON array"):
            fmp.fetch(now=NOW)


def test_fmp_rejects_malformed_event_instead_of_silently_dropping_it():
    fmp = FmpEconomicCalendarProvider("secret")
    with patch("fundamentals.calendar_feed.urlopen", return_value=FakeResponse(b'[{"event":"CPI","currency":"USD"}]')):
        with pytest.raises(CalendarFeedError, match="date is required"):
            fmp.fetch(now=NOW)


def test_fmp_environment_selection_requires_a_key(monkeypatch):
    monkeypatch.setenv("MOILBOT_CALENDAR_PROVIDER", "fmp")
    monkeypatch.delenv("MOILBOT_FMP_API_KEY", raising=False)
    assert HttpEconomicCalendarProvider.from_environment() is None


def test_unknown_provider_selection_is_rejected(monkeypatch):
    monkeypatch.setenv("MOILBOT_CALENDAR_PROVIDER", "unknown")
    with pytest.raises(CalendarFeedError, match="must be 'http' or 'fmp'"):
        HttpEconomicCalendarProvider.from_environment()
