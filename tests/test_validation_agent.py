from app.agents.validation_agent import ValidationAgent


def test_validation_agent_rejects_unsupported_report_statement() -> None:
    agent = ValidationAgent()
    result = agent.run(
        {
            "request_id": "req-1",
            "ticker": "NVDA",
            "draft_report": {
                "request_id": "req-1",
                "ticker": "NVDA",
                "company_one_liner": "Draft one liner",
                "executive_summary": ["Summary"],
                "base_case": [],
                "facts": [{"statement": "Unsupported fact", "citations": []}],
                "bull_case": [],
                "bear_case": [],
                "decision_view": "",
                "thesis_breakers": [],
                "uncertainties": [],
                "key_monitoring_items": [],
                "citations": [],
                "confidence": "low",
                "limitations": [],
            },
        }
    )

    assert result.passed is False
    assert any("facts[0]" in error.path for error in result.errors)
    assert any(error.path == "base_case" for error in result.errors)
    assert any(error.path == "bear_case" for error in result.errors)
    assert any(error.path == "decision_view" for error in result.errors)
    assert any(error.path == "thesis_breakers" for error in result.errors)
