"""Tests for Jinja filters used in telegram_report.j2."""

from __future__ import annotations

import pytest

from report_render import strip_usd_for_template


@pytest.mark.smoke
def test_strip_usd_removes_leading_dollars() -> None:
    assert strip_usd_for_template("$100") == "100"
    assert strip_usd_for_template("$$99.5") == "99.5"
    assert strip_usd_for_template(None) == ""
