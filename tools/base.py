"""Tool platform primitives (Office Hours Alt B — Ideal Architecture first).

``MOCK_APIS=1`` enables reading deterministic JSON from ``tests/fixtures/mock_data/``.
Individual @tool functions in :mod:`tools_legacy` gain mock branches incrementally.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def mock_apis_enabled() -> bool:
    return os.getenv("MOCK_APIS", "").strip().lower() in ("1", "true", "yes", "on")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_mock_json(filename: str) -> Any | None:
    """Load ``tests/fixtures/mock_data/{filename}``. Returns None if missing or invalid JSON."""
    path = _repo_root() / "tests" / "fixtures" / "mock_data" / filename
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        logger.warning("load_mock_json failed for %s: %s", filename, exc)
        return None
