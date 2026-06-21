"""Smoke tests for options_bigquery_writer.write_gex_by_strike (env-gated, idempotent)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

import options_bigquery_writer as bq
from tools.options.models import GEXResult, Provenance, StrikeGamma


def _gex() -> GEXResult:
    return GEXResult(
        underlying="MU",
        spot_price=100.0,
        total_gex=300000.0,
        call_gex=500000.0,
        put_gex=-200000.0,
        per_strike=(
            StrikeGamma(strike=95.0, call_gex=0.0, put_gex=-200000.0),
            StrikeGamma(strike=100.0, call_gex=500000.0, put_gex=0.0),
        ),
        contracts_used=2,
        provenance=Provenance(source="test", as_of=datetime(2026, 6, 20, tzinfo=timezone.utc), method="snapshot_greeks"),
    )


def test_by_strike_noop_when_table_unset(monkeypatch):
    monkeypatch.setattr(bq, "OPTIONS_GEX_BY_STRIKE_TABLE", "")
    assert bq.write_gex_by_strike(date(2026, 6, 20), _gex()) is False


@pytest.mark.smoke
def test_by_strike_builds_one_row_per_strike(monkeypatch):
    captured: list = []

    def fake_insert(table_id, rows):
        captured.append((table_id, rows))
        return True

    monkeypatch.setattr(bq, "OPTIONS_GEX_BY_STRIKE_TABLE", "proj.market_data.options_gex_by_strike")
    monkeypatch.setattr(bq, "_insert", fake_insert)

    assert bq.write_gex_by_strike(date(2026, 6, 20), _gex()) is True
    table_id, rows = captured[0]
    assert table_id == "proj.market_data.options_gex_by_strike"
    assert len(rows) == 2  # one per strike
    # deterministic insert_id + net_gex computed
    insert_id, row = rows[1]
    assert row["strike"] == 100.0
    assert row["net_gex"] == 500000.0
    assert len(insert_id) == 40  # sha1 hex
