from __future__ import annotations

from signal_quality import evaluate_signal_quality


def test_signal_quality_rewards_complete_review_time_context():
    row = {
        "signal_id": "nvda-long",
        "category": "AI",
        "asset": "NVDA",
        "direction": "LONG",
        "star_rating": 2,
        "thesis_one_liner": "AI capex and inference demand support upside",
        "status": "APPROVED_FOR_PAPER",
        "regime": "risk-on",
        "reference_entry_price": 100,
        "reference_target_price": 130,
        "reference_stop_price": 90,
        "paper_exit_price": 80,
    }

    quality = evaluate_signal_quality(row)

    assert quality["quality_score"] == 100
    assert quality["quality_grade"] == "A"
    assert "balanced_r_multiple" in quality["quality_reasons"]
    assert "approved_for_paper" in quality["quality_reasons"]


def test_signal_quality_penalizes_missing_context_and_gate_warning():
    row = {
        "signal_id": "spy-long",
        "category": "AI",
        "asset": "SPY",
        "direction": "LONG",
        "star_rating": 1,
        "thesis_one_liner": "",
        "status": "PENDING_REVIEW",
        "gate_issue_hints": ["SPY exposure check failed"],
    }

    quality = evaluate_signal_quality(row)

    assert quality["quality_score"] == 25
    assert quality["quality_grade"] == "D"
    assert "missing_entry" in quality["quality_reasons"]
    assert "gate_warning" in quality["quality_reasons"]


def test_signal_quality_ignores_later_paper_outcome():
    base = {
        "signal_id": "btc-short",
        "category": "CRYPTO",
        "asset": "BTC",
        "direction": "SHORT",
        "star_rating": 1,
        "thesis_one_liner": "ETF flow cooled while dollar liquidity tightens",
        "status": "PAPER_CLOSED",
        "reference_entry_price": 50,
        "reference_target_price": 40,
        "reference_stop_price": 55,
    }

    win = evaluate_signal_quality({**base, "paper_exit_price": 40})
    loss = evaluate_signal_quality({**base, "paper_exit_price": 60})

    assert win["quality_score"] == loss["quality_score"]
    assert win["quality_grade"] == loss["quality_grade"]
