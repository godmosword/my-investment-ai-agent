"""Smoke: scripts/backfill_data.py surface (no live BQ/FRED)."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

BACKFILL = Path(__file__).resolve().parent / "scripts" / "backfill_data.py"


def test_backfill_source_schema_field_count():
    text = BACKFILL.read_text(encoding="utf-8")
    count = len(re.findall(r'bigquery\.SchemaField\(', text))
    assert count == 13


def test_backfill_source_documents_key_metrics():
    text = BACKFILL.read_text(encoding="utf-8")
    for field in ("timestamp", "dxy", "mvrv_z_score", "exchange_netflow"):
        assert f'"{field}"' in text


def test_backfill_cli_supports_dry_run():
    text = BACKFILL.read_text(encoding="utf-8")
    assert "--dry-run" in text
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(["--dry-run"])
    assert args.dry_run is True
