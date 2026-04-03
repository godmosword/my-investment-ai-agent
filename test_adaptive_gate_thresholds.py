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
    monkeypatch.setenv("ADAPTIVE_GATE_BQ_READ", "0")
    assert agt.effective_pick_rotation_override_min_gap() == 9.0


@pytest.mark.smoke
def test_effective_pick_rotation_adds_bump_when_bq_suggests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAPTIVE_GATE_THRESHOLDS", "1")
    monkeypatch.setenv("PICK_ROTATION_OVERRIDE_MIN_GAP", "10")
    monkeypatch.setenv("ADAPTIVE_GATE_GAP_BUMP", "2.5")
    monkeypatch.setenv("ADAPTIVE_GATE_GAP_CEILING", "30")

    def _fake_bump() -> float:
        return 2.5

    monkeypatch.setattr(agt, "_bq_rotation_gap_bump", _fake_bump)
    assert agt.effective_pick_rotation_override_min_gap() == 12.5


@pytest.mark.smoke
def test_effective_pick_rotation_respects_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAPTIVE_GATE_THRESHOLDS", "1")
    monkeypatch.setenv("PICK_ROTATION_OVERRIDE_MIN_GAP", "20")
    monkeypatch.setenv("ADAPTIVE_GATE_GAP_BUMP", "10")
    monkeypatch.setenv("ADAPTIVE_GATE_GAP_CEILING", "22")

    monkeypatch.setattr(agt, "_bq_rotation_gap_bump", lambda: 10.0)
    assert agt.effective_pick_rotation_override_min_gap() == 22.0
