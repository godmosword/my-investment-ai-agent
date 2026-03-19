from __future__ import annotations

from pydantic import BaseModel


class ReportOutput(BaseModel):
    title: str
    summary: str
    code: str  # <code> 區塊
    news: str = ""


def parse_report_output(output_json: dict) -> ReportOutput:
    """Pydantic 結構驗證：若欄位缺失/型別錯誤會直接拋出例外。"""
    return ReportOutput(**output_json)


def assert_report_output(result: ReportOutput) -> None:
    """自訂 assertion：檢查摘要乾淨度、<code> 標籤與最小長度。"""
    assert "Error" not in result.summary, "摘要含有錯誤訊息"
    assert "<code>" in result.code, "缺少 <code> 標籤"
    assert len(result.summary) > 50, "摘要太短，可能是空回應"


def assert_sample_output(sample_output: dict) -> None:
    """對原始 dict 的快速防呆檢查（與 parse_report_output 互補）。"""
    assert sample_output.get("title"), "title 不能為空"
    assert "<code>" in sample_output.get("code", ""), "code block 缺失"
    assert "HTTPError" not in sample_output.get("news", ""), "news 含有 API error"
