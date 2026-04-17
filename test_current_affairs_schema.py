"""Phase 5: CurrentAffairsRoundtable / RoundtableVoice schema (safe default: env off)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas import CurrentAffairsRoundtable, RoundtableVoice


def _voice(role: str = "宏觀", **kwargs) -> dict:
    base = {
        "role": role,
        "viewpoint": "敘述足夠長度以通過最小契約檢查。",
        "disagreement": "與其他角色在風險權重上看法不同。",
    }
    base.update(kwargs)
    return base


def test_roundtable_valid_minimal():
    r = CurrentAffairsRoundtable(
        topic="本日主題",
        voices=[
            RoundtableVoice(**_voice("宏觀")),
            RoundtableVoice(**_voice("加密")),
        ],
        consensus="短線維持觀望。",
        dashboard_anchors=["VIX"],
    )
    assert len(r.voices) == 2


def test_roundtable_rejects_too_few_voices():
    with pytest.raises(ValidationError):
        CurrentAffairsRoundtable(
            topic="x",
            voices=[RoundtableVoice(**_voice())],
            consensus="c",
            dashboard_anchors=[],
        )


def test_roundtable_evidence_anchor_must_match_whitelist():
    with pytest.raises(ValidationError, match="白名單"):
        CurrentAffairsRoundtable(
            topic="x",
            voices=[
                RoundtableVoice(**_voice("宏觀", evidence_anchor="BAD_KEY")),
                RoundtableVoice(**_voice("加密")),
            ],
            consensus="c",
            dashboard_anchors=["VIX"],
        )


def test_roundtable_requires_disagreement_on_at_least_one_voice():
    with pytest.raises(ValidationError, match="disagreement"):
        CurrentAffairsRoundtable(
            topic="x",
            voices=[
                RoundtableVoice(
                    role="宏觀",
                    viewpoint="足夠長的觀點敘述用於測試契約。",
                    disagreement=None,
                ),
                RoundtableVoice(
                    role="加密",
                    viewpoint="另一則足夠長的觀點敘述用於測試契約。",
                    disagreement=None,
                ),
            ],
            consensus="c",
            dashboard_anchors=[],
        )


@pytest.mark.smoke
def test_daily_brief_report_accepts_none_roundtable(monkeypatch):
    """Default pipeline: field omitted / None — no extra structured rules."""
    monkeypatch.delenv("BRIEF_CURRENT_AFFAIRS", raising=False)
    from test_validate_report import _make_minimal_structured_report_dbr

    r = _make_minimal_structured_report_dbr()
    assert r.current_affairs_roundtable is None


@pytest.mark.smoke
def test_daily_brief_report_validates_roundtable_when_env_on(monkeypatch):
    from test_validate_report import _make_minimal_structured_report_dbr

    monkeypatch.setenv("BRIEF_CURRENT_AFFAIRS", "1")
    base = _make_minimal_structured_report_dbr()
    rt = CurrentAffairsRoundtable(
        topic="地緣與流動性",
        voices=[
            RoundtableVoice(**_voice("宏觀")),
            RoundtableVoice(**_voice("風險")),
        ],
        unresolved=["聯準會口徑仍待確認"],
        dashboard_anchors=["VIX", "BTC_RSI14_1d"],
    )
    r = base.model_copy(update={"current_affairs_roundtable": rt})
    assert r.current_affairs_roundtable is not None
