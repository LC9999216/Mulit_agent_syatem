from app.agents.financials_agent import FinancialsAgent
from app.schemas.request import CompanyAnalysisRequest


def test_financials_agent_omits_misleading_zero_metrics_when_market_data_is_rate_limited() -> None:
    agent = FinancialsAgent()

    result = agent.run(
        {
            "request": CompanyAnalysisRequest(
                ticker="NVDA",
                user_goal="Assess whether the company merits continued tracking",
            ),
            "market_snapshot": {
                "ticker": "NVDA",
                "source_uris": {"quote": "https://financialmodelingprep.com/stable/quote?symbol=NVDA"},
                "market_data_status": "rate_limited",
                "market_data_error": "FMP rate limited endpoint quote for NVDA",
            },
        }
    )

    assert result.key_metrics_table == {}
    assert result.trend_findings == []
    assert result.quality_checks == []
    assert result.market_context == []
    assert result.confidence == "low"
    assert result.anomalies
    assert "rate-limit" in result.anomalies[0].statement.lower()


def test_financials_agent_omits_misleading_zero_metrics_when_market_data_is_unavailable() -> None:
    agent = FinancialsAgent()

    result = agent.run(
        {
            "request": CompanyAnalysisRequest(
                ticker="NVDA",
                user_goal="Assess whether the company merits continued tracking",
            ),
            "market_snapshot": {
                "ticker": "NVDA",
                "source_uris": {"quote": "https://finnhub.io/api/v1/stock/metric?symbol=NVDA"},
                "market_data_status": "unavailable",
                "market_data_error": "All configured providers failed",
                "provider": "finnhub",
            },
        }
    )

    assert result.key_metrics_table == {}
    assert result.trend_findings == []
    assert result.quality_checks == []
    assert result.market_context == []
    assert result.confidence == "low"
    assert result.anomalies
    assert "unavailable" in result.anomalies[0].statement.lower()
