import pytest

from schemas import (
    AgencyDeliverable,
    AgencyResearchOutput,
    Citation,
    DeepFilingAnalysis,
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
    """Upstream may send a section label string per question instead of list[Citation]."""
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
