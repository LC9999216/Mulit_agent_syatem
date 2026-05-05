from types import SimpleNamespace

from app.agents.thesis_agent import ThesisAgent
from app.schemas.common import Citation, StatementWithCitations
from app.schemas.financials import FinancialsOutput
from app.schemas.filings import FilingsOutput
from app.schemas.market import MarketOutput
from app.schemas.news import NewsOutput
from app.schemas.request import CompanyAnalysisRequest


class EmptyThesisLLMClient:
    def generate_structured(self, *, agent_name, model, system_prompt, user_prompt, response_model):
        return SimpleNamespace(
            parsed=response_model.model_validate(
                {
                    "company_one_liner": "",
                    "executive_summary": [],
                    "base_case": [],
                    "bear_case": [],
                    "decision_view": "",
                    "thesis_breakers": [],
                    "uncertainties": [],
                    "key_monitoring_items": [],
                    "confidence": "medium",
                }
            ),
            metadata={
                "provider": "deepseek",
                "model": model,
                "status": "completed",
                "duration_ms": 10,
                "retry_count": 0,
                "input_summary": "thesis",
                "output_summary": "empty",
                "fallback_used": False,
                "error_type": None,
            },
        )


class GenericThesisLLMClient:
    def generate_structured(self, *, agent_name, model, system_prompt, user_prompt, response_model):
        return SimpleNamespace(
            parsed=response_model.model_validate(
                {
                    "company_one_liner": "Gross margin remains strong and free cash flow remains solid.",
                    "executive_summary": [
                        "NVDA currently screens well for the stated goal.",
                        "Based on the provided evidence, the company appears well positioned.",
                    ],
                    "base_case": [],
                    "bear_case": [],
                    "decision_view": "Continue tracking NVDA.",
                    "thesis_breakers": [],
                    "uncertainties": [],
                    "key_monitoring_items": [],
                    "confidence": "medium",
                }
            ),
            metadata={
                "provider": "deepseek",
                "model": model,
                "status": "completed",
                "duration_ms": 10,
                "retry_count": 0,
                "input_summary": "thesis",
                "output_summary": "generic",
                "fallback_used": False,
                "error_type": None,
            },
        )


def _build_state_for_summary_tests() -> dict:
    filing_citation = Citation(
        source_type="filing",
        source_uri="https://www.sec.gov/example",
        label="10-K 2025-01-31",
        support_type="filing",
    )
    return {
        "request_id": "req-summary",
        "request": CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the stock still offers a decision-useful setup after a large move",
        ),
        "filings_output": FilingsOutput(
            business_summary=[
                StatementWithCitations(
                    statement="NVIDIA describes its CUDA-led software stack as a core enabler of AI and accelerated computing workloads.",
                    citations=[filing_citation],
                )
            ],
            management_claims=[],
            risk_factor_summary=[
                StatementWithCitations(
                    statement="NVIDIA flags export controls and customer concentration as risks that could pressure results.",
                    citations=[filing_citation],
                )
            ],
            material_changes=[
                StatementWithCitations(
                    statement="A recent 8-K disclosed the adoption of a fiscal 2027 compensation plan tied to revenue goals.",
                    citations=[filing_citation],
                )
            ],
            open_questions=[],
        ),
        "financials_output": FinancialsOutput(
            trend_findings=[
                StatementWithCitations(
                    statement="NVDA revenue growth remains elevated at 65%.",
                    citations=[],
                )
            ],
            quality_checks=[
                StatementWithCitations(
                    statement="Gross margin remains strong at 71%.",
                    citations=[],
                ),
                StatementWithCitations(
                    statement="Free cash flow margin is approximately 45%.",
                    citations=[],
                ),
            ],
            anomalies=[],
            market_context=[],
            citations=[],
            confidence="medium",
            key_metrics_table={},
        ),
        "market_output": MarketOutput(
            price_action_summary=[
                StatementWithCitations(
                    statement="NVDA shares are up 108% over the trailing year.",
                    citations=[],
                ),
                StatementWithCitations(
                    statement="NVDA is trading at roughly 91% of its 52-week price range.",
                    citations=[],
                ),
            ],
            valuation_view=[
                StatementWithCitations(
                    statement="Price-to-sales remains elevated near 21.0x, reinforcing how much future growth the market is already discounting.",
                    citations=[],
                )
            ],
            market_view=[
                StatementWithCitations(
                    statement="The stock has already had a strong move, so the market likely embeds elevated execution expectations for NVDA.",
                    citations=[],
                )
            ],
            citations=[],
            confidence="medium",
            key_metrics_table={},
        ),
        "news_output": NewsOutput(
            bullish_catalysts=[],
            bearish_catalysts=[],
            key_news_items=[],
            raw_events=[],
            citations=[],
            confidence="medium",
        ),
        "limitations": [],
    }


def test_thesis_agent_backfills_empty_llm_sections_into_readable_summary() -> None:
    agent = ThesisAgent(
        llm_client=EmptyThesisLLMClient(),
        settings=SimpleNamespace(
            llm_enabled=True,
            llm_model_thesis="deepseek-chat",
            llm_provider="deepseek",
        ),
    )
    filing_citation = Citation(
        source_type="filing",
        source_uri="https://www.sec.gov/example",
        label="10-K 2025-01-31",
        support_type="filing",
    )
    state = {
        "request_id": "req-test",
        "request": CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        ),
        "filings_output": FilingsOutput(
            business_summary=[
                StatementWithCitations(
                    statement="Management disclosed sustained AI infrastructure demand across hyperscale customers.",
                    citations=[filing_citation],
                )
            ],
            management_claims=[],
            risk_factor_summary=[
                StatementWithCitations(
                    statement="Customer concentration and export controls remain material risks.",
                    citations=[filing_citation],
                )
            ],
            material_changes=[],
            open_questions=[],
        ),
        "financials_output": FinancialsOutput(
            trend_findings=[
                StatementWithCitations(
                    statement="NVDA revenue growth remains elevated at 217%.",
                    citations=[],
                )
            ],
            quality_checks=[
                StatementWithCitations(
                    statement="Gross margin remains strong at 71%.",
                    citations=[],
                ),
                StatementWithCitations(
                    statement="Free cash flow margin is approximately 48%.",
                    citations=[],
                ),
            ],
            anomalies=[],
            market_context=[],
            citations=[],
            confidence="medium",
            key_metrics_table={},
        ),
        "market_output": MarketOutput(
            price_action_summary=[
                StatementWithCitations(
                    statement="NVDA shares are up 82% over the trailing year.",
                    citations=[],
                )
            ],
            valuation_view=[
                StatementWithCitations(
                    statement="Valuation remains sensitive to any slowdown from current elevated growth.",
                    citations=[],
                )
            ],
            market_view=[
                StatementWithCitations(
                    statement="The market already embeds elevated execution expectations after a strong trailing move.",
                    citations=[],
                )
            ],
            citations=[],
            confidence="medium",
            key_metrics_table={},
        ),
        "news_output": NewsOutput(
            bullish_catalysts=[
                StatementWithCitations(
                    statement="Recent AI partnership announcements support demand visibility.",
                    citations=[],
                )
            ],
            bearish_catalysts=[
                StatementWithCitations(
                    statement="Recent export-control headlines keep regulatory risk elevated.",
                    citations=[],
                )
            ],
            key_news_items=[
                StatementWithCitations(
                    statement="The company filed an 8-K describing a strategic partnership update.",
                    citations=[],
                ),
                StatementWithCitations(
                    statement="NVIDIA launched a new enterprise AI platform for data center customers.",
                    citations=[],
                ),
                StatementWithCitations(
                    statement="A forward-looking opinion piece argues Nvidia could be worth $6 trillion.",
                    citations=[],
                )
            ],
            raw_events=[
                {
                    "title": "NVIDIA files 8-K on partnership update",
                    "summary": "The company filed an 8-K describing a strategic partnership update.",
                    "source": "SEC RSS",
                    "url": "https://sec.example/nvda-8k",
                    "published_at": "2026-04-20",
                    "sentiment_tag": "neutral",
                    "topic_tag": "filing",
                    "source_class": "regulatory",
                    "source_quality": "standard",
                },
                {
                    "title": "NVIDIA launches enterprise AI platform",
                    "summary": "NVIDIA launched a new enterprise AI platform for data center customers.",
                    "source": "Reuters",
                    "url": "https://example.com/reuters",
                    "published_at": "2026-04-19",
                    "sentiment_tag": "bullish",
                    "topic_tag": "product",
                    "source_class": "market_news",
                    "source_quality": "standard",
                },
                {
                    "title": "Will Nvidia Be Worth $6 Trillion a Year From Now?",
                    "summary": "A forward-looking opinion piece argues Nvidia could be worth $6 trillion.",
                    "source": "The Motley Fool",
                    "url": "https://example.com/opinion",
                    "published_at": "2026-04-18",
                    "sentiment_tag": "bullish",
                    "topic_tag": "general",
                    "source_class": "market_news",
                    "source_quality": "opinion",
                },
            ],
            citations=[],
            confidence="medium",
        ),
        "limitations": [],
    }

    report = agent.run(state)

    assert report.company_one_liner
    assert len(report.executive_summary) >= 2
    assert any("AI" in item or "demand" in item.lower() for item in report.executive_summary)
    assert report.what_happened
    assert any("8-K" in item for item in report.what_happened)
    assert any("enterprise AI platform" in item for item in report.what_happened)
    assert all("6 trillion" not in item.lower() for item in report.what_happened)
    assert report.market_view
    assert report.price_action_summary
    assert report.valuation_view
    assert report.recent_bullish_catalysts
    assert report.recent_bearish_catalysts
    assert report.key_news_items
    assert len(report.key_news_items) == 2
    assert all("6 trillion" not in item.statement.lower() for item in report.key_news_items)
    assert report.base_case
    assert report.bear_case
    assert report.decision_view
    assert report.thesis_breakers
    assert report.thesis_breakers != [item.statement for item in report.bear_case[: len(report.thesis_breakers)]]
    assert all(("if " in item.lower()) or ("would " in item.lower()) for item in report.thesis_breakers)
    assert any("export control" in item.lower() or "customer concentration" in item.lower() for item in report.thesis_breakers)
    assert report.uncertainties
    assert report.key_monitoring_items


def test_thesis_agent_rewrites_generic_executive_summary_into_evidence_based_lines() -> None:
    agent = ThesisAgent(
        llm_client=GenericThesisLLMClient(),
        settings=SimpleNamespace(
            llm_enabled=True,
            llm_model_thesis="deepseek-chat",
            llm_provider="deepseek",
        ),
    )

    report = agent.run(_build_state_for_summary_tests())

    assert len(report.executive_summary) >= 3
    assert all("screens well for the stated goal" not in item.lower() for item in report.executive_summary)
    assert any("revenue growth remains elevated at 65%" in item.lower() for item in report.executive_summary)
    assert any("gross margin remains strong at 71%" in item.lower() or "free cash flow margin is approximately 45%" in item.lower() for item in report.executive_summary)
    assert any("market likely embeds elevated execution expectations" in item.lower() or "price-to-sales remains elevated near 21.0x" in item.lower() for item in report.executive_summary)


def test_thesis_agent_builds_what_happened_and_decision_view_from_recent_evidence() -> None:
    agent = ThesisAgent(
        llm_client=GenericThesisLLMClient(),
        settings=SimpleNamespace(
            llm_enabled=True,
            llm_model_thesis="deepseek-chat",
            llm_provider="deepseek",
        ),
    )

    report = agent.run(_build_state_for_summary_tests())

    assert any("8-k disclosed" in item.lower() or "compensation plan tied to revenue goals" in item.lower() for item in report.what_happened)
    assert any("shares are up 108% over the trailing year" in item.lower() or "91% of its 52-week price range" in item.lower() for item in report.what_happened)
    assert "execution-sensitive" in report.decision_view.lower()
    assert ("price-to-sales" in report.decision_view.lower()) or ("valuation" in report.decision_view.lower()) or ("market" in report.decision_view.lower())
