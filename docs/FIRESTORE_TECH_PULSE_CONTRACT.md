# Firestore Tech Pulse Contract

Collection: `TECH_PULSE_FIRESTORE_COLLECTION`, default `tech_pulse_memory_items`.

Required per document:
- `headline`
- `published_at`
- `source_name` or `source_domain`
- `gemini_take`

Recommended:
- `source_url`
- `pillar`
- `tags`
- `tickers`
- `confidence`
- `deep_brief`
- `thesis_breakdown`
- `language`
- `ingested_at`

Freshness levels:
- `fresh`: `published_at` is under 36 hours old.
- `stale`: `published_at` is over 36 hours old.
- `unknown`: timestamp is missing or cannot be parsed.

The API does not reject older documents. It exposes `freshness` and `missing_fields`
so `/news` and `/columns` can show provenance and data quality without fabricating
source or timing data.
