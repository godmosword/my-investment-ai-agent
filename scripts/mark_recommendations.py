#!/usr/bin/env python3
"""CLI: mark paper recommendation outcomes for Track Record snapshots.

Usage:
  python scripts/mark_recommendations.py

Writes to BigQuery only when RECOMMENDATION_OUTCOMES_TABLE is set. The command
never places orders; it reads local execution intents and uses yfinance quotes
through symbol_snapshot_service.fetch_symbol_quote.
"""

from __future__ import annotations

import json
import sys

import bigquery_writer
from execution_intents import latest_execution_intents
from symbol_snapshot_service import fetch_symbol_quote
from track_record import build_mark_to_market_rows


def main() -> int:
    intents = latest_execution_intents(limit=500, dedupe=True, sort_by="updated_desc")
    rows = build_mark_to_market_rows(intents, fetch_symbol_quote)
    bigquery_writer.write_recommendation_outcome_rows(rows)
    print(json.dumps({"written": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
