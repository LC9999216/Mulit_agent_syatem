from app.graphs.graph_factory import build_graph
from app.schemas.request import CompanyAnalysisRequest
from app.services.runtime import RuntimeServices


class StubSecClient:
    def fetch_company_documents(self, ticker: str) -> list[dict]:
        return [
            {
                "doc_type": "10-Q",
                "doc_date": "2026-04-01",
                "source_uri": "https://example.com/nvda-10q",
                "section": "Business",
                "content": "NVIDIA highlighted sustained AI infrastructure demand.",
            }
        ]


class StubMarketClient:
    def fetch_company_snapshot(self, ticker: str) -> dict:
        return {
            "ticker": ticker,
            "price": 950.0,
            "price_change_1y": 0.82,
            "year_high": 1000.0,
            "year_low": 400.0,
            "pe_ttm": 45.0,
            "price_to_sales": 22.0,
            "revenue_growth_yoy": 0.69,
            "gross_margin": 0.76,
            "fcf_margin": 0.49,
            "source_uris": {
                "quote": "https://financialmodelingprep.com/stable/quote?symbol=NVDA",
                "price_change": "https://financialmodelingprep.com/stable/stock-price-change?symbol=NVDA",
                "income_growth": "https://financialmodelingprep.com/stable/income-statement-growth?symbol=NVDA",
                "ratios": "https://financialmodelingprep.com/stable/ratios?symbol=NVDA",
                "cash_flow": "https://financialmodelingprep.com/stable/cash-flow-statement?symbol=NVDA",
            },
        }


class StubNewsClient:
    def fetch_company_news(self, ticker: str) -> list[dict]:
        return [
            {
                "title": "NVIDIA signs new AI infrastructure partnership",
                "summary": "A new partnership supports demand visibility for AI infrastructure deployments.",
                "source": "Example News",
                "url": "https://example.com/bull",
                "published_at": "2026-04-18",
                "sentiment_tag": "bullish",
                "topic_tag": "partnership",
            },
            {
                "title": "Export controls remain a risk for advanced chip shipments",
                "summary": "Regulatory restrictions could affect shipment capacity and mix.",
                "source": "Example News",
                "url": "https://example.com/bear",
                "published_at": "2026-04-17",
                "sentiment_tag": "bearish",
                "topic_tag": "regulation",
            },
        ]


def test_graph_builds_final_report_with_auditable_citations() -> None:
    graph = build_graph(
        RuntimeServices(
            sec_client=StubSecClient(),
            market_data_client=StubMarketClient(),
            news_client=StubNewsClient(),
        )
    )
    result = graph.invoke(
        {
            "request": CompanyAnalysisRequest(
                ticker="NVDA",
                user_goal="Assess whether the company merits continued tracking",
            )
        }
    )

    report = result["final_report"]
    assert report.ticker == "NVDA"
    assert report.facts
    assert result["market_output"].market_view
    assert result["news_output"].key_news_items
    assert report.citations
    assert any("financialmodelingprep.com" in citation.source_uri for citation in report.citations)
    assert result["status"] == "completed"
