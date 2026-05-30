"""Shared pytest fixtures for ``tests/api/`` contract tests."""

from __future__ import annotations

import pytest

from tests.api.helpers import make_api_client


@pytest.fixture()
def client(monkeypatch):
    return make_api_client(monkeypatch)


@pytest.fixture()
def client_skip_bq(monkeypatch):
    return make_api_client(monkeypatch, SKIP_BIGQUERY="1")


@pytest.fixture()
def client_intents(monkeypatch, tmp_path):
    store = tmp_path / "execution_intents.jsonl"
    return make_api_client(monkeypatch, EXECUTION_INTENT_STORE=str(store))


@pytest.fixture()
def client_intents_portfolio(monkeypatch, tmp_path):
    return make_api_client(
        monkeypatch,
        EXECUTION_INTENT_STORE=str(tmp_path / "execution_intents.jsonl"),
        PORTFOLIO_HOLDINGS_FILE=str(tmp_path / "portfolio_holdings.jsonl"),
    )


@pytest.fixture()
def client_portfolio(monkeypatch, tmp_path):
    return make_api_client(
        monkeypatch,
        PORTFOLIO_HOLDINGS_FILE=str(tmp_path / "portfolio_holdings.jsonl"),
    )
