from graph.graph_nodes import agency_researcher_node, deep_filing_analysis_node


def _state():
    return {
        "category": "AI",
        "price_context": "NVDA 10-Q filing and SEC earnings update",
        "exclude_context": "",
        "arbiter_summary": "",
        "deep_dive_query": "Check NVDA filing",
        "bull_arguments": [],
        "bear_arguments": [],
        "raw_news": [{"title": "NVDA filing update", "description": "SEC 10-Q"}],
        "raw_data": {},
        "proposed_trades": [{"asset": "NVDA"}],
        "graph_run_id": "test-run",
    }


def test_deep_filing_node_disabled_noop(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_ENABLED", "0")
    assert deep_filing_analysis_node(_state()) == {}


def test_deep_filing_node_builds_cited_payload(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_ENABLED", "1")
    monkeypatch.setenv("NOTEBOOKLM_NOTEBOOK_ID", "nb")

    import tools.notebooklm_tool as notebook

    def fake_query_many(questions, *, notebook_id=""):
        return {
            1: {
                "answer": "Revenue grew with cited capex context.",
                "citations": [{"page": 12, "excerpt": "Revenue and capex note"}],
            }
        }

    monkeypatch.setattr(notebook, "notebooklm_query_many", fake_query_many)
    out = deep_filing_analysis_node(_state())
    assert out["deep_filing_analysis"]["ticker"] == "NVDA"
    assert out["deep_filing_analysis"]["answers"]["1"].startswith("Revenue grew")


def test_agency_node_requires_flag_and_builds_from_deep(monkeypatch):
    state = _state()
    state["deep_filing_analysis"] = {
        "ticker": "NVDA",
        "filing_type": "10-Q",
        "answers": {1: "Capex rose."},
        "citations": {1: [{"page": 12, "excerpt": "capex note"}]},
    }
    monkeypatch.setenv("AGENCY_RESEARCH_ENABLED", "0")
    assert agency_researcher_node(state) == {}

    monkeypatch.setenv("AGENCY_RESEARCH_ENABLED", "1")
    out = agency_researcher_node(state)
    assert out["agency_research_output"]["ticker"] == "NVDA"
    assert out["agency_research_output"]["deliverables"]
