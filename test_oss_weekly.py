"""Unit tests for OSS scout weekly pipeline (no network)."""
from __future__ import annotations

import tempfile
from pathlib import Path

# Import from scripts/ (same pattern as one-off runs from repo root)
import sys

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "scripts"))

from oss_scout_candidates import build_payload  # noqa: E402
from oss_suitability import label_for_score, score_repo  # noqa: E402
from oss_weekly_pipeline import _trim_weekly_blocks, merge_todos  # noqa: E402


def test_build_payload_slims_items():
    raw = {
        "total_count": 2,
        "items": [
            {
                "full_name": "a/b",
                "html_url": "https://github.com/a/b",
                "description": "x" * 300,
                "stargazers_count": 10,
                "forks_count": 1,
                "updated_at": "2024-01-01T00:00:00Z",
                "pushed_at": "2024-01-02T00:00:00Z",
                "archived": False,
                "topics": ["quant"],
            }
        ],
    }
    p = build_payload(raw, query="q", sort="stars", per_page=20)
    assert p["query"] == "q"
    assert p["items"][0]["description"] == "x" * 240
    assert p["items"][0]["topics"] == ["quant"]


def test_score_archived():
    s, why = score_repo({"archived": True, "readme_excerpt": "x" * 500})
    assert s == 1
    assert "archived" in why


def test_label_for_score():
    assert label_for_score(5) == "建議優先評估"
    assert label_for_score(1) == "暫緩"


def test_trim_weekly_blocks():
    inner = "### 2026-03-01\n\na\n\n---\n\n### 2026-02-01\n\nb"
    out = _trim_weekly_blocks(inner, max_blocks=1)
    assert "2026-03-01" in out
    assert "2026-02-01" not in out


def test_merge_todos_inserts_section():
    d = Path(tempfile.mkdtemp()) / "TODOS.md"
    d.write_text("## 修訂紀錄\n\nold\n", encoding="utf-8")
    merge_todos(d, "2099-01-01", "- [ ] test item")
    text = d.read_text(encoding="utf-8")
    assert "<!-- OSS_SCOUT_AUTO_BEGIN -->" in text
    assert "2099-01-01" in text
    assert "- [ ] test item" in text
    assert "## 修訂紀錄" in text


def test_merge_todos_prepends_second_week():
    d = Path(tempfile.mkdtemp()) / "TODOS.md"
    d.write_text(
        "## 修訂紀錄\n\nx\n",
        encoding="utf-8",
    )
    merge_todos(d, "2099-01-01", "first")
    merge_todos(d, "2099-01-08", "second")
    text = d.read_text(encoding="utf-8")
    i = text.index("2099-01-08")
    j = text.index("2099-01-01")
    assert i < j
