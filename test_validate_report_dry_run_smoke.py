"""Gate dry-run skeleton stays in sync with validate_report."""

import sys
from pathlib import Path

import pytest

from report_html_gates import validate_report

_ROOT = Path(__file__).resolve().parent
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))
import report_skeleton_validate as _sk  # noqa: E402


@pytest.mark.smoke
def test_minimal_skeleton_passes_validate_report() -> None:
    r = validate_report(_sk.minimal_valid_report_text())
    assert r["valid"], r.get("issues")
