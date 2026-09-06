"""Repo-backed append-only JSONL state store.

GCP 移除後，原本存在 BigQuery 的管線狀態（建議、持倉、日指標）改存在
``.qsilicon/`` 之下的 JSONL。GitHub Actions runner 是 ephemeral，因此這些檔案
必須由 ``scripts/commit_state.sh`` commit 回 repo 才會跨輪存活。

路徑解析沿用 ``execution_intents._store_path`` 的慣例：相對 repo 根目錄，可用
``QSILICON_STATE_DIR`` 覆寫（測試以 tmp_path 隔離）。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_STATE_DIR = ".qsilicon"


def state_dir() -> Path:
    """The directory holding all JSONL stores."""
    raw = (os.getenv("QSILICON_STATE_DIR") or _DEFAULT_STATE_DIR).strip() or _DEFAULT_STATE_DIR
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path(__file__).resolve().parent / candidate
    return candidate


def store_path(name: str) -> Path:
    """Resolve *name* inside the state dir, refusing paths that escape it."""
    base = state_dir()
    resolved = (base / name).resolve()
    # base 本身可能尚未存在，故用 strict=False 的 resolve 再比對前綴。
    if not str(resolved).startswith(str(base.resolve()) + os.sep):
        raise ValueError(f"state store name escapes the state dir: {name!r}")
    return resolved


def read_jsonl(name: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Read every well-formed row from *name*; missing store reads as empty.

    Corrupt lines (a runner killed mid-write) are skipped with a warning rather
    than failing the whole read — the pipeline must survive a truncated tail.
    ``limit`` returns the newest rows, matching append-only tail semantics.
    """
    path = store_path(name)
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError):
        return []
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("state store read failed (%s): %s", name, exc)
        return []

    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("state store %s: skipping malformed line %d", name, lineno)
    if limit is not None and limit >= 0:
        return rows[-limit:] if limit else []
    return rows


def _serialise(rows: list[dict[str, Any]]) -> str:
    """Serialise every row up-front so a bad row cannot leave a half-written file."""
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def append_jsonl(name: str, rows: list[dict[str, Any]]) -> int:
    """Append *rows* to *name*. Returns the number of rows written."""
    if not rows:
        return 0
    payload = _serialise(rows)
    path = store_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(payload)
    return len(rows)


def replace_jsonl(name: str, rows: list[dict[str, Any]]) -> int:
    """Replace the whole contents of *name* with *rows*.

    Used where the BigQuery path did DELETE + insert (e.g. tracker's open
    positions), not for append-only logs.
    """
    payload = _serialise(rows)
    path = store_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return len(rows)
