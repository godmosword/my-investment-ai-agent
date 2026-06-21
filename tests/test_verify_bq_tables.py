"""Unit tests for scripts/verify_bq_tables.py (diagnostic, no real BigQuery)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

verify_bq_tables = importlib.import_module("verify_bq_tables")


def test_unset_table_is_optional_skip(monkeypatch):
    import config

    monkeypatch.setattr(config, "OPTIONS_GEX_BY_STRIKE_TABLE", "", raising=False)
    report = verify_bq_tables.build_report(checker=lambda t: {"status": "exists"})
    row = next(r for r in report if r["name"] == "options_gex_by_strike")
    assert row["configured"] is False
    assert "optional skip" in row["status"]
    assert row["ddl"] == "docs/SQL/options_gex_by_strike.sql"


def test_configured_table_uses_checker(monkeypatch):
    import config

    monkeypatch.setattr(config, "OPTIONS_GEX_BY_STRIKE_TABLE", "proj.market_data.options_gex_by_strike", raising=False)
    report = verify_bq_tables.build_report(checker=lambda t: {"status": "exists", "rows": 7, "fields": 9})
    row = next(r for r in report if r["name"] == "options_gex_by_strike")
    assert row["configured"] is True
    assert row["status"] == "exists"
    assert row["rows"] == 7


def test_registry_maps_ddl_and_auto_create():
    names = {r[0] for r in verify_bq_tables.TABLE_REGISTRY}
    assert {"options_gex_by_strike", "recommendation_outcomes", "paper_execution_audit"} <= names
    auto = {r[0]: r[3] for r in verify_bq_tables.TABLE_REGISTRY}
    assert auto["recommendation_outcomes"] is True  # writer auto-creates
    assert auto["options_gex_by_strike"] is False  # manual DDL


@pytest.mark.smoke
def test_main_runs_without_credentials(monkeypatch, capsys):
    # checker is the real _bq_check but no tables configured by default in test env.
    rc = verify_bq_tables.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "optional 表診斷" in out
