import pytest

from crew import build_ai_final_prompt, build_crypto_final_prompt


@pytest.mark.smoke
def test_crypto_prompt_contract_contains_required_markers():
    prompt = build_crypto_final_prompt(ctx="CTX", prev_recs_ctx="PREV", today_str="2026-03-21")
    required = [
        "QSREC_START",
        "QSREC_END",
        "〔新聞 1〕",
        "今日風險預算",
        "訊號衝突摘要",
    ]
    for token in required:
        assert token in prompt, f"missing required token: {token}"


@pytest.mark.smoke
def test_ai_prompt_contract_contains_required_markers():
    prompt = build_ai_final_prompt(ctx="CTX")
    required = [
        "QSREC_START",
        "QSREC_END",
        "〔新聞 4〕",
        "美股部位框",
        "Signal Score",
    ]
    for token in required:
        assert token in prompt, f"missing required token: {token}"


def test_prompt_contract_includes_impact_leak_guard():
    crypto_prompt = build_crypto_final_prompt(ctx="CTX", prev_recs_ctx="PREV", today_str="2026-03-21")
    ai_prompt = build_ai_final_prompt(ctx="CTX")
    guard = "IMPACT"
    assert guard in crypto_prompt
    assert guard in ai_prompt
