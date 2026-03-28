"""Offline eval: fixed report fixtures vs validate_report (ADOPTION Phase 4).

Each case under tests/fixtures/reports/<name>/ has report.txt + expected_validation.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from main import validate_report

_FIXTURES_ROOT = Path(__file__).resolve().parent / "tests" / "fixtures" / "reports"


def _fixture_dirs() -> list[Path]:
    if not _FIXTURES_ROOT.is_dir():
        return []
    return sorted(p for p in _FIXTURES_ROOT.iterdir() if p.is_dir() and (p / "report.txt").is_file())


@pytest.fixture(autouse=True)
def _stable_gate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic validate_report: no BQ rotation, no freshness/exec/tool gates."""
    monkeypatch.setenv("SKIP_BIGQUERY", "1")
    monkeypatch.setenv("STRICT_NEWS_FRESHNESS_GATE", "0")
    monkeypatch.setenv("PIPELINE_REPORT_DATE", "")
    monkeypatch.setenv("STRICT_EXEC_SUMMARY_HTML_GATE", "0")
    monkeypatch.setenv("STRICT_TOOL_EVIDENCE_GATE", "0")
    monkeypatch.setenv("PICK_ROLLING_FREQ_GATE", "0")
    monkeypatch.setenv("STRICT_MACRO_CONFLICT_GATE", "0")
    monkeypatch.setenv("DATA_MISSING_COUNT_GATE_MAX", "0")


def _assert_fixture(case_dir: Path) -> None:
    report_path = case_dir / "report.txt"
    exp_path = case_dir / "expected_validation.json"
    text = report_path.read_text(encoding="utf-8")
    expected = json.loads(exp_path.read_text(encoding="utf-8"))
    result = validate_report(text)

    assert result["valid"] is expected["valid"], (
        f"{case_dir.name}: valid mismatch: got {result['valid']}, "
        f"issues={result['issues'][:5]!r}"
    )

    n = len(result["issues"])
    if "issues_count" in expected:
        assert n == expected["issues_count"], (
            f"{case_dir.name}: issues_count want {expected['issues_count']}, got {n}: {result['issues']}"
        )
    if expected.get("issues_count_min") is not None:
        assert n >= int(expected["issues_count_min"]), (
            f"{case_dir.name}: expected >= {expected['issues_count_min']} issues, got {n}"
        )

    for sub in expected.get("issues_substrings_any") or []:
        assert any(sub in issue for issue in result["issues"]), (
            f"{case_dir.name}: no issue containing substring {sub!r} in {result['issues']}"
        )

    for key, want in (expected.get("result_flags") or {}).items():
        assert result.get(key) == want, f"{case_dir.name}: result[{key!r}] want {want!r}, got {result.get(key)!r}"


@pytest.mark.smoke
@pytest.mark.parametrize("case_dir", _fixture_dirs(), ids=lambda p: p.name)
def test_validate_report_fixture(case_dir: Path) -> None:
    _assert_fixture(case_dir)


@pytest.mark.smoke
def test_fixtures_catalog_non_empty() -> None:
    dirs = _fixture_dirs()
    assert len(dirs) >= 5, f"expected at least 5 report fixtures under {_FIXTURES_ROOT}"
