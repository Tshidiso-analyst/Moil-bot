# Economic calendar provider integration

Moil-bot accepts a provider through a small JSON-over-HTTPS contract. The repository does **not** claim a live calendar is connected until a provider URL is configured and the provider returns a fresh, coverage-certified response.

## Configure

Copy `.env.example` to `.env` and set:

- `MOILBOT_CALENDAR_URL`: absolute HTTP(S) endpoint that returns the schema below. Use HTTPS for hosted providers.
- `MOILBOT_CALENDAR_TOKEN`: optional bearer token, if required by the provider.
- `MOILBOT_CALENDAR_TIMEOUT`: request timeout in seconds (default 8).
- `MOILBOT_CALENDAR_MAX_AGE_SECONDS`: maximum age of the provider's `fetched_at` timestamp (default 900 seconds).
- `MOILBOT_CALENDAR_SYMBOLS`: comma-separated symbols for event alerts (default EURUSD,GBPUSD,USDJPY,XAUUSD).
- `MOILBOT_CALENDAR_POLL_SECONDS`: polling interval (default 300 seconds; minimum 30).

Restart the dashboard after changing environment variables. The background monitor starts when a URL is configured. If the URL is blank, invalid, stale, incomplete or unreachable, the dashboard reports the calendar as unverified and the real-time pipeline blocks new-trade approval.

## Required response contract

```json
{
  "source": "provider-name",
  "fetched_at": "2026-11-07T12:00:00Z",
  "coverage_start": "2026-11-07T00:00:00Z",
  "coverage_end": "2026-11-14T00:00:00Z",
  "events": [
    {
      "name": "US CPI",
      "currency": "USD",
      "scheduled_at": "2026-11-10T13:30:00Z",
      "impact": "high",
      "actual": null,
      "forecast": 3.1,
      "previous": 3.0,
      "surprise_bias": "context_dependent",
      "source_url": "https://provider.example/events/us-cpi"
    }
  ]
}
```

All timestamps must be ISO-8601 with an explicit timezone. Event impact must be `high`, `medium`, `low` or `unknown`. Actual, forecast and previous values are numeric or null. The provider must identify itself and explicitly certify the coverage interval. An empty events array is valid only when the provider certifies that interval.

## Runtime behaviour

- Polls the configured endpoint in a background daemon thread.
- Rejects stale feeds, invalid timestamps, missing source/coverage metadata, malformed events and oversized responses.
- Creates warning alerts for matching high-impact events approaching within 60 minutes and critical alerts inside the 30-minute-before / 15-minute-after blackout.
- Generates alerts for the configured symbols and deduplicates repeated events within the running process.
- Exposes feed status in the Analysis dashboard.
- Passes verified calendar status and active high-impact event state to the real-time pipeline.
- Does not infer a directional trade from the event. The macro-bias gate remains closed until a separately verified, aligned macro assessment is supplied.
- Does not close existing positions and does not enable MT5 order execution.

## Provider selection

Choose a calendar vendor whose licence permits your intended use and whose data includes the currencies, event importance, release times, forecasts and revisions needed by the strategy. If the vendor does not return this exact response, place a small adapter service in front of it that maps its documented API response into this contract. Do not paste a vendor API key into source code or commit it to GitHub.
