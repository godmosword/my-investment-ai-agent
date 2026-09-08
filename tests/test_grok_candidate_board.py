"""Governance contract for the Grok weekly quota board (Human B, 2026-09-08)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / ".grok" / "CANDIDATE_BOARD.md"
CHARTER = ROOT / ".grok" / "TEAM_CHARTER.md"
ROUTINES = ROOT / ".grok" / "ROUTINES.md"
PROTOCOL = ROOT / ".grok" / "ITERATION_PROTOCOL.md"
DIGEST = ROOT / ".grok" / "templates" / "WEEKLY_DIGEST.md"

ACTIVE_STATUSES = {"NEW", "READY", "AUTHORIZED", "IN_FLIGHT"}


def _table_rows(markdown: str, heading: str) -> list[list[str]]:
    lines = markdown.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i
            break
    assert start is not None, f"missing heading {heading}"
    rows: list[list[str]] = []
    seen_header = False
    for line in lines[start + 1 :]:
        if line.startswith("## ") and rows:
            break
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and set(cells[0]) <= {"-", ":"}:
            seen_header = True
            continue
        if not seen_header:
            continue
        rows.append(cells)
    return rows


def test_board_quota_keys_and_size():
    text = BOARD.read_text(encoding="utf-8")
    for key in (
        "STANDING_WEEKLY_QUOTA: ENABLED",
        "QUOTA_SIZE: 1",
        "QUOTA_WINDOW: ISO_WEEK_UTC",
        "QUOTA_RISK: R0|R1",
        "QUOTA_MIN_PRIORITY: 8",
        "ROUTINE_IMPLEMENTATION_AUTONOMY: DISABLED",
        "CURRENT_WINDOW:",
        "QUOTA_USED:",
        "QUOTA_CONSUMED_ID:",
    ):
        assert key in text, key
    assert "PAUSE_WEEKLY_QUOTA" in text
    rows = _table_rows(text, "## Board")
    assert 1 <= len(rows) <= 7
    for row in rows:
        assert len(row) >= 7
        assert row[4] in {"R0", "R1", "R2", "R3"}
        assert row[6] in ACTIVE_STATUSES | {"DONE", "DEFERRED", "REJECTED"}
        float(row[5])
    active = [r for r in rows if r[6] in ACTIVE_STATUSES]
    assert len(active) <= 7


def test_charter_and_routines_keep_daily_scan_read_only():
    charter = CHARTER.read_text(encoding="utf-8")
    routines = ROUTINES.read_text(encoding="utf-8")
    protocol = PROTOCOL.read_text(encoding="utf-8")
    assert "STANDING_WEEKLY_QUOTA" in charter
    assert "ROUTINE_IMPLEMENTATION_AUTONOMY` remains `DISABLED`" in routines
    assert "Do **not** dispatch Engineer to implement" in routines
    assert "CANDIDATE_BOARD.md" in routines
    assert "CANDIDATE_BOARD.md" in protocol
    assert "QUOTA_MIN_PRIORITY" in protocol
    assert DIGEST.is_file()
    digest = DIGEST.read_text(encoding="utf-8")
    assert "QUOTA CONSUMED" in digest
    assert "Do not implement from this file" in digest
