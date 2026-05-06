from report_render import render_telegram_daily_brief
from schemas import (
    AgencyDeliverable,
    AgencyResearchOutput,
    Citation,
    DeepFilingAnalysis,
)
from test_telegram_template_modularization import _report_minimal


def test_optional_research_blocks_render_only_in_full_profile():
    report = _report_minimal()
    ai = report.ai.model_copy(
        update={
            "deep_filing_analysis": DeepFilingAnalysis(
                ticker="NVDA",
                filing_type="10-Q",
                answers={1: "Capex rose with cited evidence."},
                citations={1: [Citation(page=12, excerpt="capex note")]},
            ),
            "agency_research_output": AgencyResearchOutput(
                ticker="NVDA",
                deliverables=[
                    AgencyDeliverable(
                        name="Checklist",
                        content="Validate AI capex.",
                        confidence="low",
                        citations=[Citation(section="filing", excerpt="capex note")],
                    )
                ],
            ),
        }
    )
    enriched = report.model_copy(update={"ai": ai})

    full = render_telegram_daily_brief(enriched, profile="full")
    lite = render_telegram_daily_brief(enriched, profile="lite")

    assert "深度財報／申報文件核讀" in full
    assert "Agency 財務研究補充" in full
    assert "深度財報／申報文件核讀" not in lite
    assert "Agency 財務研究補充" not in lite
