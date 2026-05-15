"""Unit tests for paper_execution tick (M5)."""

import json
import subprocess
import sys
from pathlib import Path

from paper_execution import run_paper_execution_tick


def test_paper_execution_import_does_not_require_telebot():
    script = """
import builtins
import sys

original_import = builtins.__import__

def blocked_import(name, *args, **kwargs):
    if name == "telebot" or name.startswith("telebot."):
        raise ModuleNotFoundError("No module named 'telebot'")
    return original_import(name, *args, **kwargs)

for module_name in list(sys.modules):
    if module_name in {"paper_execution", "bigquery_writer", "telegram_sender"} or module_name.startswith("telebot"):
        sys.modules.pop(module_name, None)

builtins.__import__ = blocked_import
import paper_execution
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parent,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_paper_tick_long_filled(monkeypatch, tmp_path: Path):
    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "t1",
                "created_at": "2026-04-01T00:00:00Z",
                "category": "CRYPTO",
                "asset": "BTC",
                "direction": "LONG",
                "star_rating": 1,
                "status": "APPROVED_FOR_PAPER",
                "reference_entry_price": 100.0,
                "reference_target_price": 120.0,
                "reference_stop_price": 90.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    monkeypatch.setattr(
        "paper_execution.fetch_symbol_quote",
        lambda _a: {"last": 105.0, "as_of": "2026-04-02T00:00:00Z", "error": None},
    )

    written = run_paper_execution_tick()
    assert len(written) == 1
    assert written[0]["status"] == "PAPER_FILLED"
    assert written[0]["paper_fill_price"] == 105.0

    lines = store.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_paper_tick_long_stop(monkeypatch, tmp_path: Path):
    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "t2",
                "created_at": "2026-04-01T00:00:00Z",
                "category": "CRYPTO",
                "asset": "BTC",
                "direction": "LONG",
                "star_rating": 1,
                "status": "APPROVED_FOR_PAPER",
                "reference_entry_price": 100.0,
                "reference_target_price": 120.0,
                "reference_stop_price": 95.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    monkeypatch.setattr(
        "paper_execution.fetch_symbol_quote",
        lambda _a: {"last": 94.0, "as_of": "2026-04-02T00:00:00Z", "error": None},
    )

    written = run_paper_execution_tick()
    assert len(written) == 1
    assert written[0]["status"] == "PAPER_CLOSED"
    assert written[0]["paper_exit_price"] == 95.0


def test_paper_tick_skips_without_reference_prices(monkeypatch, tmp_path: Path):
    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "t3",
                "created_at": "2026-04-01T00:00:00Z",
                "category": "CRYPTO",
                "asset": "BTC",
                "direction": "LONG",
                "star_rating": 1,
                "status": "APPROVED_FOR_PAPER",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    monkeypatch.setattr(
        "paper_execution.fetch_symbol_quote",
        lambda _a: {"last": 999.0, "error": None},
    )
    assert run_paper_execution_tick() == []


def test_paper_tick_calls_bigquery_audit_when_table_set(monkeypatch, tmp_path: Path):
    calls: list[dict] = []

    def fake_write(**kwargs):
        calls.append(kwargs)

    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "bq1",
                "created_at": "2026-04-01T00:00:00Z",
                "category": "CRYPTO",
                "asset": "ETH",
                "direction": "LONG",
                "star_rating": 1,
                "status": "APPROVED_FOR_PAPER",
                "reference_entry_price": 10.0,
                "reference_target_price": 20.0,
                "reference_stop_price": 5.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    monkeypatch.setattr(
        "paper_execution.fetch_symbol_quote",
        lambda _a: {"last": 12.0, "as_of": "2026-04-02T12:00:00Z", "error": None},
    )
    monkeypatch.setattr("bigquery_writer.write_paper_execution_audit_row", fake_write)

    run_paper_execution_tick()
    assert len(calls) == 1
    assert calls[0]["signal_id"] == "bq1"
    assert calls[0]["new_status"] == "PAPER_FILLED"
    assert calls[0]["asset"] == "ETH"
    assert calls[0]["direction"] == "LONG"
    assert calls[0]["quote_as_of"] == "2026-04-02T12:00:00Z"
    assert calls[0]["source"] == "paper_tick"
