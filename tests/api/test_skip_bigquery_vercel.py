"""skip_bigquery: explicit env wins; Vercel defaults to skip."""

from __future__ import annotations

import pytest

from api_deps import skip_bigquery


@pytest.mark.smoke
def test_skip_bigquery_unset_without_vercel(monkeypatch):
    monkeypatch.delenv("SKIP_BIGQUERY", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    assert skip_bigquery() is False


@pytest.mark.smoke
@pytest.mark.parametrize("value", ["1", "true", "YES"])
def test_skip_bigquery_explicit_true(monkeypatch, value):
    monkeypatch.setenv("SKIP_BIGQUERY", value)
    monkeypatch.setenv("VERCEL", "1")
    assert skip_bigquery() is True


@pytest.mark.smoke
@pytest.mark.parametrize("value", ["0", "false", "no"])
def test_skip_bigquery_explicit_false_wins_on_vercel(monkeypatch, value):
    monkeypatch.setenv("SKIP_BIGQUERY", value)
    monkeypatch.setenv("VERCEL", "1")
    assert skip_bigquery() is False


@pytest.mark.smoke
def test_skip_bigquery_unset_defaults_true_on_vercel(monkeypatch):
    monkeypatch.delenv("SKIP_BIGQUERY", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    assert skip_bigquery() is True
