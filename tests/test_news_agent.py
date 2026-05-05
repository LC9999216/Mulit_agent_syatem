from app.agents.news_agent import NewsAgent
from app.schemas.request import CompanyAnalysisRequest


def test_news_agent_splits_bullish_and_bearish_catalysts() -> None:
    agent = NewsAgent()

    result = agent.run(
        {
            "request": CompanyAnalysisRequest(
                ticker="NVDA",
                user_goal="Assess recent catalysts",
            ),
            "news_events": [
                {
                    "title": "NVIDIA expands AI partnership with hyperscaler",
                    "summary": "The company announced a new AI infrastructure partnership expected to support demand.",
                    "source": "Example News",
                    "url": "https://example.com/bull",
                    "published_at": "2026-04-18",
                    "sentiment_tag": "bullish",
                    "topic_tag": "partnership",
                },
                {
                    "title": "New export controls could affect advanced chip shipments",
                    "summary": "New regulatory restrictions may pressure shipment capacity and product mix.",
                    "source": "Example News",
                    "url": "https://example.com/bear",
                    "published_at": "2026-04-17",
                    "sentiment_tag": "bearish",
                    "topic_tag": "regulation",
                },
            ],
        }
    )

    assert result.bullish_catalysts
    assert result.bearish_catalysts
    assert result.key_news_items
    assert len(result.raw_events) == 2


def test_news_agent_keeps_regulatory_events_out_of_bull_bear_buckets() -> None:
    agent = NewsAgent()

    result = agent.run(
        {
            "request": CompanyAnalysisRequest(
                ticker="NVDA",
                user_goal="Assess recent catalysts",
            ),
            "news_events": [
                {
                    "title": "NVIDIA files 8-K on partnership update",
                    "summary": "The company filed an 8-K, signaling a current report event that may require review of the disclosed update.",
                    "source": "SEC RSS",
                    "url": "https://sec.example/nvda-8k",
                    "published_at": "2026-04-20",
                    "sentiment_tag": "neutral",
                    "topic_tag": "filing",
                    "source_class": "regulatory",
                }
            ],
        }
    )

    assert not result.bullish_catalysts
    assert not result.bearish_catalysts
    assert len(result.key_news_items) == 1


def test_news_agent_keeps_opinion_articles_out_of_bull_bear_buckets() -> None:
    agent = NewsAgent()

    result = agent.run(
        {
            "request": CompanyAnalysisRequest(
                ticker="NVDA",
                user_goal="Assess recent catalysts",
            ),
            "news_events": [
                {
                    "title": "Will Nvidia Be Worth $6 Trillion a Year From Now?",
                    "summary": "A forward-looking opinion piece about Nvidia's upside.",
                    "source": "The Motley Fool",
                    "url": "https://example.com/opinion",
                    "published_at": "2026-04-20",
                    "sentiment_tag": "bullish",
                    "topic_tag": "general",
                    "source_class": "market_news",
                    "source_quality": "opinion",
                }
            ],
        }
    )

    assert not result.bullish_catalysts
    assert not result.bearish_catalysts
    assert len(result.key_news_items) == 0


def test_news_agent_prioritizes_standard_news_over_opinion_in_key_news() -> None:
    agent = NewsAgent()

    result = agent.run(
        {
            "request": CompanyAnalysisRequest(
                ticker="NVDA",
                user_goal="Assess recent catalysts",
            ),
            "news_events": [
                {
                    "title": "Will Nvidia Be Worth $6 Trillion a Year From Now?",
                    "summary": "A forward-looking opinion piece about Nvidia's upside.",
                    "source": "The Motley Fool",
                    "url": "https://example.com/opinion",
                    "published_at": "2026-04-20",
                    "sentiment_tag": "bullish",
                    "topic_tag": "general",
                    "source_class": "market_news",
                    "source_quality": "opinion",
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
            ],
        }
    )

    assert result.key_news_items[0].statement.startswith("NVIDIA launched")
    assert len(result.key_news_items) == 1


def test_news_agent_prioritizes_high_quality_publishers_in_key_news() -> None:
    agent = NewsAgent()

    result = agent.run(
        {
            "request": CompanyAnalysisRequest(
                ticker="NVDA",
                user_goal="Assess recent catalysts",
            ),
            "news_events": [
                {
                    "title": "NVIDIA launches enterprise AI platform",
                    "summary": "NVIDIA launched a new enterprise AI platform for data center customers.",
                    "source": "Reuters",
                    "url": "https://example.com/reuters",
                    "published_at": "2026-04-19",
                    "sentiment_tag": "bullish",
                    "topic_tag": "product",
                    "source_class": "market_news",
                    "source_quality": "high",
                },
                {
                    "title": "NVIDIA expands AI partnership",
                    "summary": "NVIDIA expanded an AI partnership.",
                    "source": "Benzinga",
                    "url": "https://example.com/benzinga",
                    "published_at": "2026-04-20",
                    "sentiment_tag": "bullish",
                    "topic_tag": "partnership",
                    "source_class": "market_news",
                    "source_quality": "standard",
                },
            ],
        }
    )

    assert result.key_news_items[0].statement.startswith("NVIDIA launched")


def test_news_agent_backfills_bull_bear_and_news_when_external_news_is_sparse() -> None:
    agent = NewsAgent()

    result = agent.run(
        {
            "request": CompanyAnalysisRequest(
                ticker="NVDA",
                user_goal="Assess recent catalysts",
            ),
            "news_events": [],
            "filings_output": {
                "material_changes": [
                    {
                        "statement": "NVIDIA filed an 8-K tied to quarterly results and management commentary.",
                        "citations": [],
                    }
                ],
                "risk_factor_summary": [
                    {
                        "statement": "Export controls and customer concentration remain material risks.",
                        "citations": [],
                    }
                ],
            },
            "financials_output": {
                "quality_checks": [
                    {
                        "statement": "Gross margin remains strong at 71%.",
                        "citations": [],
                    }
                ]
            },
            "market_output": {
                "latest_price_analysis": [
                    {
                        "statement": "NVDA is extended after a strong rally and trades near the top of its range.",
                        "citations": [],
                    }
                ],
                "valuation_view": [
                    {
                        "statement": "Price-to-sales remains elevated near 21.0x.",
                        "citations": [],
                    }
                ],
            },
        }
    )

    assert result.important_news
    assert result.bullish_factors
    assert result.bearish_factors
