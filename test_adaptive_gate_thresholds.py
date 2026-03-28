"""Smoke tests for adaptive_gate_thresholds."""

import pytest

import adaptive_gate_thresholds as agt


@pytest.mark.smoke
def test_effective_pick_rotation_respects_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADAPTIVE_GATE_THRESHOLDS", raising=False)
    monkeypatch.setenv("PICK_ROTATION_OVERRIDE_MIN_GAP", "15.5")
    assert agt.effective_pick_rotation_override_min_gap() == 15.5


@pytest.mark.smoke
def test_effective_pick_rotation_adaptive_flag_still_returns_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAPTIVE_GATE_THRESHOLDS", "1")
    monkeypatch.setenv("PICK_ROTATION_OVERRIDE_MIN_GAP", "9")
    assert agt.effective_pick_rotation_override_min_gap() == 9.0
