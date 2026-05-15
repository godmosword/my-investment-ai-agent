# Earnings Insight Scaffold (queue 45 / P3)

`GET /api/earnings/{symbol}/insight` reads a JSONL file pointed at by
`DEEP_FILING_ANALYSIS_FILE` (default `data/deep_filing_analysis.jsonl`).
The endpoint **never fabricates content** — if no row exists for the
requested ticker, it returns `enabled: false` with an explicit reason
so the UI can render an empty state honestly.

This doc explains how to:

1. Try the endpoint locally with the committed example template.
2. Replace the template with real NotebookLM / agency output.
3. Append new filings over time without overwriting history.

## 1. Try it locally

The repo ships **`data/deep_filing_analysis.example.jsonl`** with three
clearly-watermarked **TEMPLATE** rows (NVDA, AMD, MSFT). Every answer
and citation is prefixed with `TEMPLATE —` to make it obvious that the
content is structural, not real analysis.

```bash
# Backend
cp data/deep_filing_analysis.example.jsonl data/deep_filing_analysis.jsonl
uvicorn api:app --reload --port 8000

# PWA (separate terminal)
cd data-verification-ui
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

Open `http://localhost:5173/insights?tab=earnings`:

- The calendar list comes from `GET /api/earnings/upcoming` and depends on
  `yfinance` reaching the public calendar API. If it fails (network or
  rate-limited), the list shows an empty state — that is correct behaviour,
  not a bug.
- Clicking **NVDA** / **AMD** / **MSFT** opens the scaffold panel. You
  will see the TEMPLATE strings — that is your cue to paste real
  NotebookLM output.

Use **`EARNINGS_WATCHLIST_OVERRIDE`** to constrain the watchlist for
demos:

```bash
EARNINGS_WATCHLIST_OVERRIDE=NVDA,AMD,MSFT uvicorn api:app --reload
```

## 2. Replace template with real output

Each row in `data/deep_filing_analysis.jsonl` must match the
`DeepFilingAnalysis` schema:

```jsonc
{
  "ticker": "NVDA",
  "filing_type": "10-Q",           // free-text label
  "as_of": "2026-05-22",            // ISO date or any sortable string
  "answers": {
    "1": "Datacenter revenue ... (paste actual figure + 1-sentence driver)",
    "2": "Gross margin ... (paste actual %)"
  },
  "citations": {
    // every answer key MUST have at least one citation; schema rejects orphans
    "1": [{ "section": "MD&A — Datacenter", "excerpt": "verbatim quote from the 10-Q" }],
    "2": [{ "section": "Gross margin discussion", "excerpt": "verbatim quote" }]
  },
  "red_flags": ["concise bullet if any; leave [] when clean"]
}
```

**Hard rules:**

- `citations[k].excerpt` must be a **verbatim** excerpt from the source
  filing or press release; do not paraphrase, do not summarize.
- If you only have a paraphrase, leave the answer out — do not store a
  paraphrase as a "citation". The whole point of the citation contract
  is to let the UI link back to source.
- Every answer key needs at least one citation entry — the Pydantic
  validator (`schemas.DeepFilingAnalysis._require_citations_for_answers`)
  rejects orphans and the API will return `enabled: false` with
  `reason: "scaffold_invalid"` if it sees one.

## 3. Append new filings, never overwrite

The endpoint returns **the newest row per ticker** (sorted by `as_of`
descending). To preserve history, append a new line per filing rather
than rewriting the file:

```bash
# After NVDA next 10-Q:
echo '{"ticker":"NVDA","filing_type":"10-Q","as_of":"2026-08-22", ... }' \
  >> data/deep_filing_analysis.jsonl
```

The file is under `.gitignore` (only the `.example.jsonl` template is
committed). Back it up if it contains valuable analysis.

## 4. Schema quick-reference

| Field | Type | Notes |
|-------|------|-------|
| `ticker` | str | Uppercased on read; matches `/api/earnings/{symbol}/insight` path arg |
| `filing_type` | str | Free-text label (`10-Q`, `10-K`, `S-1`, `8-K`, etc.) |
| `as_of` | str | Sortable string; ISO date recommended |
| `answers` | `{int: str}` | Question index → answer text. Empty strings dropped. |
| `citations` | `{int: [Citation]}` | Every answer key must appear here with ≥1 entry |
| `red_flags` | `[str]` | Optional bullet list |
| `Citation.excerpt` | str | Required; verbatim source quote |
| `Citation.section` | str? | Optional; section label (e.g., "MD&A — Datacenter") |
| `Citation.page` | int? / str? | Optional; page or locator |

See [`schemas.py:1209`](../schemas.py) (`DeepFilingAnalysis`) for the
authoritative shape.

## 5. Related red lines

- The endpoint does not call any LLM or external service. All content
  comes from the JSONL file.
- The endpoint does not write to the file. Update it via your own
  ingestion pipeline (NotebookLM run output, manual paste from
  earnings transcripts, etc.).
- New external data sources to feed this file must be reviewed under
  [`docs/REALTIME_DATA_SOURCES_GOVERNANCE.md`](REALTIME_DATA_SOURCES_GOVERNANCE.md)
  before being treated as production. Internal NotebookLM scaffold output
  is not an external source and does not require governance review.
