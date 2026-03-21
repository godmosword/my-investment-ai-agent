"""
Phase 3 — dual-run validation compare（僅觀測、不切正式輸出）。

legacy = main.validate_report
candidate = main._validate_report_candidate（預留重構後第二路徑）

當兩路 snapshot 不一致時，由 main 以 WARNING 記錄；Telegram / BQ 仍只信賴 legacy 結果。
"""

from __future__ import annotations

# 用於比對的穩定欄位（避免 dict 內無關鍵值漂移）
_SNAPSHOT_KEYS: tuple[str, ...] = (
    "valid",
    "news_count",
    "fallback_news_count",
    "has_data_missing",
    "has_qsrec",
    "qsrec_count",
    "has_source_health",
    "has_source_errors",
    "has_source_quota",
    "has_mixed_regime",
    "has_unactionable_trade",
    "has_macro_outlier",
    "has_macro_conflict",
    "has_source_observability_conflict",
    "trade_watch_mode",
    "partial_news_ok",
    "news_six_relaxed",
    "pick_justification_crypto_ok",
    "pick_justification_equity_ok",
    "pick_rotation_crypto_ok",
    "pick_rotation_equity_ok",
)


def validation_snapshot(result: dict) -> dict:
    """將 validate_report 回傳 dict 壓成可比對、可序列化的快照。"""
    issues = list(result.get("issues") or [])
    snap: dict = {k: result.get(k) for k in _SNAPSHOT_KEYS}
    snap["issues_sorted"] = sorted(issues)
    return snap


def compare_validation_results(legacy: dict, candidate: dict) -> dict:
    """
    比對兩次驗證結果。

    Returns:
        identical: 快照是否完全一致
        legacy_valid / candidate_valid
        issues_only_in_legacy / issues_only_in_candidate（集合差集，方便掃一眼）
        snapshot_legacy / snapshot_candidate（除錯用）
    """
    sl = validation_snapshot(legacy)
    sc = validation_snapshot(candidate)
    identical = sl == sc
    il = set(sl["issues_sorted"])
    ic = set(sc["issues_sorted"])
    return {
        "identical": identical,
        "legacy_valid": bool(legacy.get("valid")),
        "candidate_valid": bool(candidate.get("valid")),
        "issues_only_in_legacy": sorted(il - ic),
        "issues_only_in_candidate": sorted(ic - il),
        "snapshot_legacy": sl,
        "snapshot_candidate": sc,
    }
