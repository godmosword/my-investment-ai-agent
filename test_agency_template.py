import importlib


def test_agency_template_disabled(monkeypatch):
    monkeypatch.setenv("AGENCY_RESEARCH_ENABLED", "0")
    import agents.agency as agency

    importlib.reload(agency)
    assert agency._load_agency_template("investment_researcher.md") == ""
    assert agency.load_agency_template().summary() == ""


def test_agency_template_parser(monkeypatch):
    monkeypatch.setenv("AGENCY_RESEARCH_ENABLED", "1")
    import agents.agency as agency

    importlib.reload(agency)
    tpl = agency.load_agency_template("investment_researcher.md")
    assert "Q-Silicon" in tpl.core_mission
    assert tpl.critical_rules
    assert tpl.deliverables
    assert "Core Mission:" in tpl.summary()
