"""
戰報結構驗證 — 候選入口（Phase 3）。

目前實作：延遲 import `main.validate_report`，與 legacy 完全等價。
日後可在此改為獨立實作（例如僅依賴 validation_rules + 純函式），
並持續用 REPORT_COMPARE_MODE=1 觀測與 legacy 的 snapshot 差異。

注意：模組頂層不可 import main，否則可能造成載入順序循環。
"""

from __future__ import annotations


def validate_report_candidate(text: str) -> dict:
    """
    候選驗證路徑。正式管線仍以 main.validate_report 為唯一權威。

    Returns:
        與 main.validate_report 相同結構的 dict。
    """
    import main as _main  # noqa: PLC0415 — 延遲匯入避免 import cycle

    return _main.validate_report(text)
