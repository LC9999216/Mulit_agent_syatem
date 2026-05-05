from pydantic import ValidationError

from app.schemas.request import CompanyAnalysisRequest
from app.schemas.report import FinalReport


def test_company_analysis_request_requires_ticker_and_defaults() -> None:
    request = CompanyAnalysisRequest(ticker="nvda", user_goal="Assess tracking fit")

    assert request.ticker == "NVDA"
    assert request.include_market is True
    assert request.include_risk is False


def test_company_analysis_request_rejects_blank_user_goal() -> None:
    try:
        CompanyAnalysisRequest(ticker="NVDA", user_goal="  ")
    except ValidationError as exc:
        assert "user_goal" in str(exc)
    else:
        raise AssertionError("Expected blank user_goal to raise ValidationError")


def test_final_report_serializes_citations() -> None:
    report = FinalReport.model_validate(
        {
            "request_id": "req-1",
            "ticker": "NVDA",
            "company_one_liner": "NVDA remains an AI infrastructure leader.",
            "executive_summary": ["Revenue momentum remains elevated."],
            "what_happened": ["Recent filings and market data support continued attention."],
            "market_view": ["The market is pricing in continued strong execution."],
            "latest_price_analysis": ["Price remains above key support and near recent highs."],
            "price_action_summary": ["Shares have materially outperformed over the last year."],
            "valuation_view": ["Valuation remains sensitive to growth normalization."],
            "recent_bullish_catalysts": [
                {
                    "statement": "AI infrastructure demand remains a clear positive catalyst.",
                    "citations": [
                        {
                            "source_type": "news",
                            "source_uri": "https://example.com/news-bull",
                            "label": "Bullish catalyst",
                        }
                    ],
                }
            ],
            "recent_bearish_catalysts": [
                {
                    "statement": "Export controls remain an active downside catalyst.",
                    "citations": [
                        {
                            "source_type": "news",
                            "source_uri": "https://example.com/news-bear",
                            "label": "Bearish catalyst",
                        }
                    ],
                }
            ],
            "key_news_items": [
                {
                    "statement": "Recent coverage remains centered on AI demand and regulatory risk.",
                    "citations": [
                        {
                            "source_type": "news",
                            "source_uri": "https://example.com/news",
                            "label": "Key news",
                        }
                    ],
                }
            ],
            "important_news": [
                {
                    "statement": "An earnings-related 8-K remains the most material recent event.",
                    "citations": [
                        {
                            "source_type": "news",
                            "source_uri": "https://example.com/news",
                            "label": "Important news",
                        }
                    ],
                }
            ],
            "bullish_factors": [
                {
                    "statement": "Margins and cash generation remain supportive.",
                    "citations": [],
                }
            ],
            "bearish_factors": [
                {
                    "statement": "Valuation leaves less room for execution misses.",
                    "citations": [],
                }
            ],
            "facts": [
                {
                    "statement": "Revenue grew materially year over year.",
                    "citations": [
                        {
                            "source_type": "filing",
                            "source_uri": "https://example.com/10q",
                            "label": "FY2026 Q1 10-Q",
                        }
                    ],
                }
            ],
            "short_term_plan": {
                "horizon": "short_term",
                "bias": "bullish",
                "entry_context": "Buy pullbacks into support.",
                "target_price": 1125.0,
                "stop_loss": 980.0,
                "position_size_pct": 12.0,
                "rationale": ["Momentum remains supportive."],
                "invalidators": ["A break of support invalidates the setup."],
            },
            "mid_term_plan": {
                "horizon": "mid_term",
                "bias": "bullish",
                "entry_context": "Scale in while the uptrend remains intact.",
                "target_price": 1250.0,
                "stop_loss": 920.0,
                "position_size_pct": 20.0,
                "rationale": ["Fundamentals remain strong."],
                "invalidators": ["A break of intermediate trend support invalidates the setup."],
            },
            "long_term_thesis": ["CUDA and AI infrastructure scale remain the core long-term thesis."],
            "long_term_conditions": ["Demand must remain strong."],
            "bull_case": [],
            "bear_case": [],
            "uncertainties": ["Demand durability beyond hyperscalers remains uncertain."],
            "key_monitoring_items": ["Data center revenue growth"],
            "citations": [
                {
                    "source_type": "filing",
                    "source_uri": "https://example.com/10q",
                    "label": "FY2026 Q1 10-Q",
                }
            ],
            "confidence": "medium",
            "limitations": [],
        }
    )

    dumped = report.model_dump()
    assert dumped["ticker"] == "NVDA"
    assert dumped["citations"][0]["label"] == "FY2026 Q1 10-Q"
    assert dumped["recent_bullish_catalysts"][0]["statement"].startswith("AI infrastructure")
    assert dumped["short_term_plan"]["position_size_pct"] == 12.0
