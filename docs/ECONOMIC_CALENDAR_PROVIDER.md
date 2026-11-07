# Economic calendar provider integration

Moil-bot supports a provider through a small JSON-over-HTTPS contract and includes an optional adapter for the Financial Modeling Prep (FMP) economic calendar. The repository does **not** claim a live calendar is connected until credentials are configured and a fresh response is validated.

## FMP provider (recommended adapter)

FMP documents the endpoint `https://financialmodelingprep.com/stable/economic-calendar`. Its response includes event date, country, event name, currency, previous, estimate, actual and impact. FMP documents event timestamps as UTC and limits each requested date range to 90 days.

FMP calendar access is not included in its Basic/free plan. Its current pricing matrix lists the Economic Data Releases Calendar on Starter with a date range of up to one year, and broader access on Premium and Ultimate. Pricing currently lists Starter at US$19/month when billed annually (regular monthly price shown as US$29); prices and entitlements can change, so verify the live pricing matrix before subscribing. FMP also states that displaying or redistributing its data requires a specific Data Display and Licensing Agreement. Confirm that your intended private or public Moil-bot deployment is permitted before showing provider data to other users. Do not assume that creating a free API key grants access.

Set these values in your local `.env` file:

- `MOILBOT_CALENDAR_PROVIDER=fmp`
- `MOILBOT_FMP_API_KEY`: your FMP API key (never commit it).
- `MOILBOT_FMP_CALENDAR_DAYS`: requested horizon from 1 to 90 days (default 7).
- `MOILBOT_FMP_CALENDAR_COUNTRY`: optional ISO country code, e.g. `US`; blank requests all countries.
- `MOILBOT_CALENDAR_TIMEOUT`: request timeout in seconds (default 8).
- `MOILBOT_CALENDAR_MAX_AGE_SECONDS`: maximum accepted snapshot age (default 900 seconds).

The adapter requests the current UTC date through the configured horizon, maps FMP's documented fields to Moil-bot's event model, and records the successful retrieval time. FMP does not return its own fetch timestamp or an explicit coverage certificate; the adapter therefore treats the successfully requested date range as the coverage window. A failed request, malformed response, missing key, stale snapshot or unknown impact classification cannot be used as verified high-impact event coverage. Confirm provider entitlements and data behaviour before relying on this integration in live decision workflows.

## Generic HTTP provider

Copy `.env.example` to `.env` and set:

- `MOILBOT_CALENDAR_PROVIDER=http` (or leave the default).
- `MOILBOT_CALENDAR_URL`: absolute HTTPS endpoint that returns the schema below.
- `MOILBOT_CALENDAR_TOKEN`: optional bearer token, if required by the provider.
- `MOILBOT_CALENDAR_TIMEOUT`: request timeout in seconds (default 8).
- `MOILBOT_CALENDAR_MAX_AGE_SECONDS`: maximum age of the provider's `fetched_at` timestamp (default 900 seconds).
- `MOILBOT_CALENDAR_SYMBOLS`: comma-separated symbols for event alerts (default EURUSD,GBPUSD,USDJPY,XAUUSD).
- `MOILBOT_CALENDAR_POLL_SECONDS`: polling interval (default 300 seconds; minimum 30).

The generic provider requires the upstream service to explicitly identify its source and certify its coverage interval.

## Required generic response contract

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

All timestamps must be ISO-8601 with an explicit timezone. Event impact must be `high`, `medium`, `low` or `unknown`. Actual, forecast and previous values are numeric or null.

## Runtime behaviour

- Polls the configured endpoint in a background daemon thread.
- Rejects stale feeds, invalid timestamps, missing source/coverage metadata, malformed events and oversized responses.
- Creates warning alerts for matching high-impact events approaching within 60 minutes and critical alerts inside the 30-minute-before / 15-minute-after blackout.
- Generates alerts for the configured symbols and deduplicates repeated events within the running process.
- Exposes feed status in the Analysis dashboard.
- Passes verified calendar status and active high-impact event state to the real-time pipeline.
- Does not infer a directional trade from the event. The macro-bias gate remains closed until a separately verified, aligned macro assessment is supplied.
- Does not close existing positions and does not enable MT5 order execution.
- No provider is considered live until a real account entitlement and successful authenticated response have been verified.
