# Forex education source registry

This registry tracks the 40 requested Forex education leads plus five additional
collections (EarnForex, FX Replay, CloackX, ICT Education and Infobooks).

## Important status

These entries are discovery leads, not verified URLs, endorsements, or permission
to copy material. All 45 entries intentionally start with:

- `access_status=not_verified`
- `license_status=unknown`
- `redistribution_allowed=false`
- `download_allowed=false`
- `review_status=not_reviewed`

A source must be checked individually. A free-to-read page is not automatically
free to redistribute. Do not bypass registration, paywalls, robots/access
controls, or other restrictions. Prefer official APIs, permitted downloads,
open licences, and public-domain materials whose status is confirmed for the
relevant jurisdiction.

## Registry fields

Each record tracks its category, source type, official/source URLs, access and
licence status, redistribution/download permissions, ingestion status and human
review status. Keep source attribution and original publication metadata when
extracting material.

## Safe workflow

1. Verify the publisher and canonical official URL.
2. Review terms of use, copyright and licence for the specific item.
3. Record access method and permission; do not infer permission from availability.
4. Download only direct documents with verified redistribution permission.
5. For online courses, index only material that may lawfully be accessed and
   processed; retain source links and attribution.
6. Extract, deduplicate and classify content, preserving page/lesson references.
7. Treat extracted strategy descriptions as research candidates only.
8. Require human review, explicit entry/invalidation/exit definitions, and
   independent backtesting before a strategy rule can be approved.

The registry helper module is read-only and fails closed. It does not scrape,
download, or approve trading rules.
