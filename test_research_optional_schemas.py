import pytest

from schemas import (
    AgencyDeliverable,
    AgencyResearchOutput,
    AISection,
    Citation,
    DeepFilingAnalysis,
    MetricLine,
    NewsItem,
    TradeRecommendation,
)


def test_deep_filing_analysis_requires_citations():
    with pytest.raises(ValueError, match="missing citation"):
        DeepFilingAnalysis(answers={1: "answer"}, citations={})

    model = DeepFilingAnalysis(
        ticker="NVDA",
        filing_type="10-Q",
        answers={1: "Capex rose."},
        citations={1: [Citation(page=12, excerpt="capex disclosure")]},
    )
    assert model.answers[1] == "Capex rose."


def test_deep_filing_analysis_coerces_string_citation_values():
    model = DeepFilingAnalysis(
        ticker="NVDA",
        filing_type="10-Q",
        answers={1: "Revenue note."},
        citations={1: "Section 1, Financial Performance"},
    )
    assert len(model.citations[1]) == 1
    assert model.citations[1][0].excerpt == "Section 1, Financial Performance"


def test_agency_research_output_requires_cited_deliverables():
    with pytest.raises(ValueError, match="requires at least one citation"):
        AgencyDeliverable(name="x", content="y", confidence="low", citations=[])

    with pytest.raises(ValueError, match="requires at least one deliverable"):
        AgencyResearchOutput(deliverables=[])

    model = AgencyResearchOutput(
        ticker="MSFT",
        deliverables=[
            AgencyDeliverable(
                name="Checklist",
                content="Validate AI capex.",
                confidence="low",
                citations=[Citation(section="filing", excerpt="capex note")],
            )
        ],
    )
    assert model.deliverables[0].citations[0].excerpt == "capex note"


def test_aisection_drops_invalid_agency_research_output():
    ai = AISection.model_validate(
        {
            "dashboard": [MetricLine(label="NVDA", value="100", change="0%")],
            "news": [
                NewsItem(
                    index=i,
                    timestamp_line="[05/22 10:00 UTC+8]",
                    title=f"Headline {i}",
                    source_and_nature="Source",
                    summary="Summary.",
                    investment_takeaway="NVDA filing context.",
                    editor_consensus="Neutral.",
                    pricing_note="大致已定價",
                )
                for i in (4, 5, 6)
            ],
            "pick_reason": "Filing-driven setup.",
            "signal_conflict_summary": "多空一致。",
            "trade_legs": [],
            "qsrec": [
                TradeRecommendation(
                    asset="NVDA",
                    direction="LONG",
                    current_price=100.0,
                    entry=99.0,
                    target=110.0,
                    stop=95.0,
                    confidence=3,
                    category="EQUITY",
                    trigger="Filing",
                    invalidation="Break stop",
                    position_pct=6,
                    timeframe="5-10天",
                    narrative="Filing clarity supports the long thesis.",
                    bull_scenario="Filing supports upside.",
                    bear_scenario="Macro headwinds cap gains.",
                    base_scenario="Hold above entry on filing clarity.",
                )
            ],
            "agency_research_output": {
                "agent_type": "investment_researcher",
                "ticker": "NVDA",
                "deliverables": [],
                "success_metrics": {"fallback_template": "true"},
            },
        }
    )
    assert ai.agency_research_output is None
