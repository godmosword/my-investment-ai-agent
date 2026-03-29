"""Property-based checks for pure helpers (no LLM / no live HTTP)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from telegram_sender import sanitize_telegram_html

pytestmark = [pytest.mark.boundary, pytest.mark.slow]


@settings(max_examples=80, deadline=None)
@given(st.text(max_size=400))
def test_sanitize_telegram_html_never_raises_and_returns_str(s: str) -> None:
    out = sanitize_telegram_html(s)
    assert isinstance(out, str)
