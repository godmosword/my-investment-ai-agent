"""Property-based checks for pure helpers (no LLM / no live HTTP)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from telegram_sender import sanitize_telegram_html
from report_render import strip_usd_for_template

pytestmark = [pytest.mark.boundary, pytest.mark.slow]


@settings(max_examples=80, deadline=None)
@given(st.text(max_size=400))
def test_sanitize_telegram_html_never_raises_and_returns_str(s: str) -> None:
    out = sanitize_telegram_html(s)
    assert isinstance(out, str)


@settings(max_examples=60, deadline=None)
@given(st.text())
def test_strip_usd_for_template_never_raises_and_strips_leading_dollars(s: str) -> None:
    out = strip_usd_for_template(s)
    assert isinstance(out, str)
    assert not out.startswith("$")
