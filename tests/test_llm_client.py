import json

import httpx

from app.config import Settings
from app.schemas.llm import ThesisDraftOutput
from app.services.llm_client import DeepSeekLLMClient, OpenAILLMClient, build_llm_client


def test_build_llm_client_returns_deepseek_client_when_provider_is_deepseek() -> None:
    settings = Settings(
        llm_enabled=True,
        llm_provider="deepseek",
        openai_api_key="deepseek-key",
        openai_base_url="https://api.deepseek.com",
    )

    client = build_llm_client(settings)

    assert isinstance(client, DeepSeekLLMClient)


def test_build_llm_client_returns_openai_client_when_provider_is_openai() -> None:
    settings = Settings(
        llm_enabled=True,
        llm_provider="openai",
        openai_api_key="openai-key",
        openai_base_url="https://api.openai.com/v1",
    )

    client = build_llm_client(settings)

    assert isinstance(client, OpenAILLMClient)


def test_settings_resolve_llm_model_uses_provider_compatible_fallback_for_deepseek() -> None:
    settings = Settings(
        llm_enabled=True,
        llm_provider="deepseek",
        openai_api_key="deepseek-key",
        openai_base_url="https://api.deepseek.com/v1",
        llm_model_supervisor="deepseek-chat",
        llm_model_thesis="deepseek-chat",
        llm_model_validation="deepseek-chat",
    )

    assert settings.llm_model_filings == "gpt-4o-mini"
    assert settings.resolve_llm_model("filings") == "deepseek-chat"


def test_settings_resolve_llm_model_keeps_openai_default_when_provider_is_openai() -> None:
    settings = Settings(
        llm_enabled=True,
        llm_provider="openai",
        openai_api_key="openai-key",
        openai_base_url="https://api.openai.com/v1",
    )

    assert settings.resolve_llm_model("filings") == "gpt-4o-mini"


def test_deepseek_client_uses_chat_completions_json_mode() -> None:
    captured_request: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["path"] = request.url.path
        captured_request["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "company_one_liner": "DeepSeek summary",
                                    "executive_summary": ["json output works"],
                                    "uncertainties": [],
                                    "key_monitoring_items": ["margin"],
                                    "confidence": "medium",
                                }
                            ),
                        },
                    }
                ],
            },
        )

    client = DeepSeekLLMClient(
        api_key="deepseek-key",
        base_url="https://api.deepseek.com",
        timeout_seconds=10.0,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com"),
    )

    result = client.generate_structured(
        agent_name="thesis",
        model="deepseek-chat",
        system_prompt="Return JSON only.",
        user_prompt="Write thesis.",
        response_model=ThesisDraftOutput,
    )

    assert captured_request["path"] == "/chat/completions"
    assert captured_request["body"]["response_format"] == {"type": "json_object"}
    assert "JSON" in captured_request["body"]["messages"][0]["content"]
    assert result.parsed.company_one_liner == "DeepSeek summary"
    assert result.metadata["provider"] == "deepseek"


def test_deepseek_client_normalizes_common_schema_mismatches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-456",
                "object": "chat.completion",
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "company_one_liner": "Normalized summary",
                                    "executive_summary": "One paragraph summary.",
                                    "uncertainties": [],
                                    "key_monitoring_items": "gross margin",
                                    "confidence": 80,
                                }
                            ),
                        },
                    }
                ],
            },
        )

    client = DeepSeekLLMClient(
        api_key="deepseek-key",
        base_url="https://api.deepseek.com",
        timeout_seconds=10.0,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com"),
    )

    result = client.generate_structured(
        agent_name="thesis",
        model="deepseek-chat",
        system_prompt="Return JSON only.",
        user_prompt="Write thesis.",
        response_model=ThesisDraftOutput,
    )

    assert result.parsed.executive_summary == ["One paragraph summary."]
    assert result.parsed.key_monitoring_items == ["gross margin"]
    assert result.parsed.confidence == "high"


def test_deepseek_client_maps_alternative_summary_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-789",
                "object": "chat.completion",
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "assessment": "Alternative one-liner",
                                    "executive_summary": ["Summary line"],
                                    "uncertainties": [],
                                    "key_monitoring_items": [],
                                    "confidence": "Low",
                                }
                            ),
                        },
                    }
                ],
            },
        )

    client = DeepSeekLLMClient(
        api_key="deepseek-key",
        base_url="https://api.deepseek.com",
        timeout_seconds=10.0,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com"),
    )

    result = client.generate_structured(
        agent_name="thesis",
        model="deepseek-chat",
        system_prompt="Return JSON only.",
        user_prompt="Write thesis.",
        response_model=ThesisDraftOutput,
    )

    assert result.parsed.company_one_liner == "Alternative one-liner"
    assert result.parsed.confidence == "low"


def test_deepseek_client_normalizes_nested_thesis_payload_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-thesis-nested",
                "object": "chat.completion",
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "ticker": "NVDA",
                                    "stronger_conclusion_supported": True,
                                    "bull_case": {
                                        "core_argument": "NVDA is a platform leader in AI infrastructure.",
                                        "key_points": [
                                            "Revenue growth remains elevated",
                                            "Gross margin remains strong",
                                        ],
                                        "actionable_implication": "Continue tracking NVDA as a quality compounder.",
                                    },
                                    "bear_case": {
                                        "core_argument": "Competition and cyclicality could pressure growth.",
                                        "key_points": [
                                            "Growth could moderate",
                                            "Competition could erode pricing",
                                        ],
                                        "actionable_implication": "Watch for margin compression and competitive threats.",
                                    },
                                    "thesis_breakers": {
                                        "bull_thesis_breakers": [
                                            "CUDA loses ecosystem dominance",
                                            "Gross margin falls below 60%",
                                        ],
                                        "bear_thesis_breakers": [
                                            "Growth stays above 50% for several years"
                                        ],
                                    },
                                }
                            ),
                        },
                    }
                ],
            },
        )

    client = DeepSeekLLMClient(
        api_key="deepseek-key",
        base_url="https://api.deepseek.com",
        timeout_seconds=10.0,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com"),
    )

    result = client.generate_structured(
        agent_name="thesis",
        model="deepseek-chat",
        system_prompt="Return JSON only.",
        user_prompt="Write thesis.",
        response_model=ThesisDraftOutput,
    )

    assert result.parsed.company_one_liner == "NVDA is a platform leader in AI infrastructure."
    assert result.parsed.base_case == ["Revenue growth remains elevated", "Gross margin remains strong"]
    assert result.parsed.bear_case == ["Growth could moderate", "Competition could erode pricing"]
    assert result.parsed.thesis_breakers == ["CUDA loses ecosystem dominance", "Gross margin falls below 60%"]
    assert result.parsed.decision_view == "Continue tracking NVDA as a quality compounder."


def test_deepseek_client_normalizes_flat_thesis_aliases() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-thesis-flat",
                "object": "chat.completion",
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "ticker": "NVDA",
                                    "bull_case": "NVDA benefits from a durable software moat and strong profitability.",
                                    "bear_case": "Growth could normalize and pressure valuation expectations.",
                                    "thesis_breaker": "CUDA loses ecosystem dominance.",
                                }
                            ),
                        },
                    }
                ],
            },
        )

    client = DeepSeekLLMClient(
        api_key="deepseek-key",
        base_url="https://api.deepseek.com",
        timeout_seconds=10.0,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com"),
    )

    result = client.generate_structured(
        agent_name="thesis",
        model="deepseek-chat",
        system_prompt="Return JSON only.",
        user_prompt="Write thesis.",
        response_model=ThesisDraftOutput,
    )

    assert result.parsed.company_one_liner == "NVDA benefits from a durable software moat and strong profitability."
    assert result.parsed.bear_case == ["Growth could normalize and pressure valuation expectations."]
    assert result.parsed.thesis_breakers == ["CUDA loses ecosystem dominance."]
