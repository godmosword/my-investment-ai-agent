"""Shared helpers for ``tests/api/`` HTTP contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from api import app


def write_jsonl_rows(path: Path | str, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def make_api_client(monkeypatch, **env: str | None) -> TestClient:
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, str(value))
    return TestClient(app)
