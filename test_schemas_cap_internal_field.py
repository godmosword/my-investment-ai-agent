"""G-8: property test for schemas._cap_internal_field (internal field length guard)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from schemas import _cap_internal_field

pytestmark = pytest.mark.boundary


@settings(max_examples=50, deadline=None)
@given(st.text(max_size=8000))
def test_cap_internal_field_never_exceeds_max_len(s: str) -> None:
    out = _cap_internal_field(s, max_len=4000)
    assert isinstance(out, str)
    assert len(out) <= 4000


@settings(max_examples=30, deadline=None)
@given(st.one_of(st.none(), st.integers(), st.floats(allow_nan=False), st.booleans()))
def test_cap_internal_field_passthrough_non_str(v) -> None:
    assert _cap_internal_field(v, max_len=10) == v
