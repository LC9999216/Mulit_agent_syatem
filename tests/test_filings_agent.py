from types import SimpleNamespace

from app.agents.filings_agent import FilingsAgent
from app.schemas.request import CompanyAnalysisRequest


def test_filings_agent_extracts_structured_output_from_sec_sections_without_llm() -> None:
    agent = FilingsAgent()
    state = {
        "request": CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        ),
        "documents": [
            {
                "doc_type": "10-K",
                "doc_date": "2026-02-25",
                "source_uri": "https://www.sec.gov/example-10k",
                "content": "NVIDIA serves hyperscale demand. Revenue increased because of AI deployments. Customer concentration remains a risk.",
                "sections": [
                    {
                        "section": "Business",
                        "content": "NVIDIA serves hyperscale and enterprise demand for accelerated computing and AI infrastructure.",
                    },
                    {
                        "section": "MD&A",
                        "content": "Revenue increased due to strong data center demand and new AI deployments.",
                    },
                    {
                        "section": "Risk Factors",
                        "content": "Results may fluctuate based on customer concentration and supply constraints.",
                    },
                ],
            },
            {
                "doc_type": "8-K",
                "doc_date": "2026-03-06",
                "source_uri": "https://www.sec.gov/example-8k",
                "content": "The company reported quarterly revenue growth driven by data center products.",
                "sections": [
                    {
                        "section": "Item 2.02",
                        "content": "The company reported quarterly revenue growth driven by data center products.",
                    }
                ],
            },
        ],
    }

    result = agent.run(state)

    assert result.business_summary
    assert any("accelerated computing" in item.statement.lower() for item in result.business_summary)
    assert result.management_claims
    assert any(
        "revenue" in item.statement.lower() and ("data center" in item.statement.lower() or "ai deployments" in item.statement.lower())
        for item in result.management_claims
    )
    assert result.risk_factor_summary
    assert any("customer concentration" in item.statement.lower() for item in result.risk_factor_summary)
    assert result.material_changes
    assert any("quarterly revenue growth" in item.statement.lower() for item in result.material_changes)
    assert result.open_questions == []


def test_filings_agent_prefers_readable_summary_sentences_over_raw_section_leads() -> None:
    agent = FilingsAgent()
    state = {
        "request": CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        ),
        "documents": [
            {
                "doc_type": "10-K",
                "doc_date": "2026-02-25",
                "source_uri": "https://www.sec.gov/example-10k",
                "content": "",
                "sections": [
                    {
                        "section": "Business",
                        "content": (
                            "Our Company NVIDIA pioneered accelerated computing to help solve the most challenging computational problems. "
                            "NVIDIA is now a data center scale AI infrastructure company reshaping all industries. "
                            "Its software stack accelerates AI model training and inference, data analytics, scientific computing, robotics, and 3D graphics."
                        ),
                    },
                    {
                        "section": "MD&A",
                        "content": (
                            "The following discussion and analysis of our financial condition and results of operations should be read in conjunction with Item 1A. "
                            "Revenue growth in fiscal year 2026 was driven by data center compute and networking platforms for accelerated computing and AI solutions."
                        ),
                    },
                ],
            }
        ],
    }

    result = agent.run(state)

    assert result.business_summary
    assert "our company" not in result.business_summary[0].statement.lower()
    assert "cuda-led software stack" in result.business_summary[0].statement.lower()
    assert len(result.business_summary[0].statement) < 180
    assert result.management_claims
    assert "the following discussion and analysis" not in result.management_claims[0].statement.lower()
    assert "revenue growth" in result.management_claims[0].statement.lower()
    assert "data center compute and networking" in result.management_claims[0].statement.lower()
    assert len(result.management_claims[0].statement) < 180


def test_filings_agent_rewrites_risk_and_material_change_into_short_auditable_summary() -> None:
    agent = FilingsAgent()
    state = {
        "request": CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        ),
        "documents": [
            {
                "doc_type": "10-K",
                "doc_date": "2026-02-25",
                "source_uri": "https://www.sec.gov/example-10k",
                "content": "",
                "sections": [
                    {
                        "section": "Risk Factors",
                        "content": (
                            "Compliance with existing or future governmental regulations, including import and export requirements and tariffs, "
                            "could further increase our costs, impact our competitive position, and otherwise may have a material adverse impact "
                            "on our business, financial condition and results of operations in subsequent periods."
                        ),
                    },
                ],
            },
            {
                "doc_type": "8-K",
                "doc_date": "2026-03-06",
                "source_uri": "https://www.sec.gov/example-8k",
                "content": "",
                "sections": [
                    {
                        "section": "Item 5.02",
                        "content": (
                            "Adoption of Fiscal Year 2027 Variable Compensation Plan. On March 2, 2026, the Compensation Committee adopted "
                            "the Variable Compensation Plan for Fiscal Year 2027, which provides eligible executive officers a variable cash "
                            "payment tied to achievement of specified fiscal year 2027 revenue performance goals."
                        ),
                    }
                ],
            },
        ],
    }

    result = agent.run(state)

    assert result.risk_factor_summary
    assert "regulatory" in result.risk_factor_summary[0].statement.lower()
    assert "increase costs" in result.risk_factor_summary[0].statement.lower() or "adversely affect" in result.risk_factor_summary[0].statement.lower()
    assert len(result.risk_factor_summary[0].statement) < 190
    assert result.material_changes
    assert "fiscal 2027 variable compensation plan" in result.material_changes[0].statement.lower()
    assert "revenue-based performance goals" in result.material_changes[0].statement.lower()
    assert len(result.material_changes[0].statement) < 190


class StructuredFilingsLLMClient:
    def generate_structured(self, *, agent_name, model, system_prompt, user_prompt, response_model):
        assert agent_name == "filings"
        return SimpleNamespace(
            parsed=response_model.model_validate(
                {
                    "business_summary": [
                        "NVIDIA disclosed sustained hyperscale demand for AI infrastructure."
                    ],
                    "management_claims": [
                        "Management attributed revenue growth to strong data center demand."
                    ],
                    "risk_factor_summary": [
                        "Customer concentration and supply constraints remain material risks."
                    ],
                    "material_changes": [
                        "A recent 8-K highlighted quarterly growth driven by data center products."
                    ],
                    "open_questions": [
                        "How durable is the current AI deployment cycle across major customers?"
                    ],
                }
            ),
            metadata={
                "provider": "deepseek",
                "model": model,
                "status": "completed",
                "duration_ms": 15,
                "retry_count": 0,
                "input_summary": "filings",
                "output_summary": "filings ok",
                "fallback_used": False,
                "error_type": None,
            },
        )


def test_filings_agent_uses_llm_to_compress_evidence_when_available() -> None:
    agent = FilingsAgent(
        llm_client=StructuredFilingsLLMClient(),
        settings=SimpleNamespace(
            llm_enabled=True,
            llm_model_filings="deepseek-chat",
        ),
    )
    state = {
        "request_id": "req-test",
        "request": CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        ),
        "documents": [
            {
                "doc_type": "10-K",
                "doc_date": "2026-02-25",
                "source_uri": "https://www.sec.gov/example-10k",
                "content": "NVIDIA serves hyperscale demand and reported AI-led data center growth.",
                "sections": [
                    {
                        "section": "Business",
                        "content": "NVIDIA serves hyperscale and enterprise demand for accelerated computing and AI infrastructure.",
                    },
                    {
                        "section": "MD&A",
                        "content": "Revenue increased due to strong data center demand and new AI deployments.",
                    },
                    {
                        "section": "Risk Factors",
                        "content": "Results may fluctuate based on customer concentration and supply constraints.",
                    },
                ],
            },
            {
                "doc_type": "8-K",
                "doc_date": "2026-03-06",
                "source_uri": "https://www.sec.gov/example-8k",
                "content": "The company reported quarterly revenue growth driven by data center products.",
                "sections": [
                    {
                        "section": "Item 2.02",
                        "content": "The company reported quarterly revenue growth driven by data center products.",
                    }
                ],
            },
        ],
    }

    result = agent.run(state)

    assert result.business_summary[0].statement.startswith("NVIDIA disclosed sustained hyperscale demand")
    assert result.management_claims[0].citations
    assert result.risk_factor_summary[0].citations
    assert result.material_changes[0].citations
    assert result.open_questions
