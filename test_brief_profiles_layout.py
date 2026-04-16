"""Phase 4b: optional BRIEF_LAYOUT_FILE YAML merge into profile_block_ids."""

from __future__ import annotations

from pathlib import Path

import pytest

from brief_profiles import PROFILES, profile_block_ids
from brief_profiles_layout import merge_profile_blocks_from_file

_ROOT = Path(__file__).resolve().parent
_EXAMPLE_LITE = _ROOT / "config" / "brief_layouts" / "example_lite_reorder.yaml"


def test_merge_no_env_returns_baseline(monkeypatch):
    monkeypatch.delenv("BRIEF_LAYOUT_FILE", raising=False)
    assert profile_block_ids("lite") == PROFILES["lite"]


@pytest.mark.smoke
def test_profile_block_ids_lite_reorder_via_example_yaml(monkeypatch):
    monkeypatch.setenv("BRIEF_LAYOUT_FILE", str(_EXAMPLE_LITE.relative_to(_ROOT)))
    expected = (
        "header",
        "exec_summary",
        "market_mode",
        "ai_trades",
        "crypto_trades",
        "qsrec",
    )
    assert profile_block_ids("lite") == expected


def test_merge_explicit_path_reorder():
    base = PROFILES["lite"]
    out = merge_profile_blocks_from_file(
        "lite",
        base,
        layout_path=str(_EXAMPLE_LITE),
    )
    assert out[3] == "ai_trades"
    assert out[4] == "crypto_trades"


def test_merge_applies_to_profile_mismatch_ignored(monkeypatch, tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(
        "applies_to_profile: full\nblocks:\n  - header\n  - exec_summary\n  - market_mode\n  - crypto_trades\n  - ai_trades\n  - qsrec\n",
        encoding="utf-8",
    )
    base = PROFILES["lite"]
    out = merge_profile_blocks_from_file("lite", base, layout_path=str(p))
    assert out == base


def test_merge_missing_file_returns_baseline(monkeypatch):
    monkeypatch.setenv("BRIEF_LAYOUT_FILE", str(_ROOT / "nonexistent_layout.yaml"))
    assert profile_block_ids("full") == PROFILES["full"]


def test_merge_unknown_block_raises(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(
        "applies_to_profile: lite\nblocks:\n  - header\n  - exec_summary\n  - market_mode\n  - not_a_block\n  - crypto_trades\n  - qsrec\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="whitelist"):
        merge_profile_blocks_from_file("lite", PROFILES["lite"], layout_path=str(p))


def test_merge_wrong_set_raises(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(
        "applies_to_profile: lite\nblocks:\n  - header\n  - exec_summary\n  - market_mode\n  - crypto_trades\n  - qsrec\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="every block"):
        merge_profile_blocks_from_file("lite", PROFILES["lite"], layout_path=str(p))


def test_merge_duplicate_raises(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(
        "applies_to_profile: lite\nblocks:\n  - header\n  - header\n  - exec_summary\n  - market_mode\n  - crypto_trades\n  - ai_trades\n  - qsrec\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        merge_profile_blocks_from_file("lite", PROFILES["lite"], layout_path=str(p))
