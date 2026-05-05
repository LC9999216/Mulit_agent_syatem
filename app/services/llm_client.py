import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeVar

import httpx
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class LLMClientError(Exception):
    pass


class LLMUnavailableError(LLMClientError):
    pass


@dataclass
class StructuredLLMResult:
    parsed: BaseModel
    metadata: dict


class BaseLLMClient(ABC):
    @abstractmethod
    def generate_structured(
        self,
        *,
        agent_name: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> StructuredLLMResult:
        raise NotImplementedError


class NullLLMClient(BaseLLMClient):
    def generate_structured(
        self,
        *,
        agent_name: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> StructuredLLMResult:
        raise LLMUnavailableError("LLM is disabled or no API key is configured.")


class OpenAILLMClient(BaseLLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        sleep_fn=None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.sleep_fn = sleep_fn or time.sleep
        self.http_client = http_client or httpx.Client(base_url=self.base_url, timeout=timeout_seconds)

    def generate_structured(
        self,
        *,
        agent_name: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> StructuredLLMResult:
        attempts = self.max_retries + 1
        started_at = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = self.http_client.post(
                    "/responses",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "instructions": system_prompt,
                        "input": user_prompt,
                        "store": False,
                        "text": {
                            "format": {
                                "type": "json_schema",
                                "name": response_model.__name__,
                                "strict": True,
                                "schema": response_model.model_json_schema(),
                            }
                        },
                    },
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise LLMClientError(f"OpenAI request failed with status {response.status_code}")
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") and payload["status"] != "completed":
                    raise LLMClientError(f"OpenAI response status was {payload['status']}")

                output_text = payload.get("output_text") or self._extract_output_text(payload.get("output", []))
                if not output_text:
                    raise LLMClientError("OpenAI response did not include output text.")

                parsed = response_model.model_validate(json.loads(output_text))
                usage = payload.get("usage", {})
                duration_ms = int((time.perf_counter() - started_at) * 1000)
                return StructuredLLMResult(
                    parsed=parsed,
                    metadata={
                        "provider": "openai",
                        "model": model,
                        "status": "completed",
                        "duration_ms": duration_ms,
                        "retry_count": attempt - 1,
                        "input_summary": self._truncate(user_prompt),
                        "output_summary": self._truncate(output_text),
                        "fallback_used": False,
                        "error_type": None,
                        "usage": {
                            "input_tokens": usage.get("input_tokens"),
                            "output_tokens": usage.get("output_tokens"),
                            "total_tokens": usage.get("total_tokens"),
                        },
                    },
                )
            except (httpx.HTTPError, json.JSONDecodeError, LLMClientError) as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                self.sleep_fn(float(attempt))

        raise LLMClientError(str(last_error) if last_error is not None else "LLM call failed.")

    @staticmethod
    def _extract_output_text(output_items: list[dict]) -> str:
        chunks: list[str] = []
        for item in output_items:
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    chunks.append(content["text"])
        return "".join(chunks)

    @staticmethod
    def _truncate(value: str, limit: int = 280) -> str:
        compact = " ".join(value.split())
        if len(compact) <= limit:
            return compact
        return f"{compact[: limit - 3]}..."


class DeepSeekLLMClient(BaseLLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        sleep_fn=None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.sleep_fn = sleep_fn or time.sleep
        self.http_client = http_client or httpx.Client(base_url=self.base_url, timeout=timeout_seconds)

    def generate_structured(
        self,
        *,
        agent_name: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> StructuredLLMResult:
        attempts = self.max_retries + 1
        started_at = time.perf_counter()
        last_error: Exception | None = None

        enhanced_system_prompt = (
            f"{system_prompt}\n\n"
            "Return valid JSON only. The response must be a single JSON object that matches the required schema."
        )

        for attempt in range(1, attempts + 1):
            try:
                response = self.http_client.post(
                    "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": enhanced_system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise LLMClientError(f"DeepSeek request failed with status {response.status_code}")
                response.raise_for_status()
                payload = response.json()
                choice = (payload.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                output_text = message.get("content")
                if not output_text:
                    raise LLMClientError("DeepSeek response did not include message content.")

                parsed_payload = self._normalize_payload(json.loads(output_text), response_model)
                parsed = response_model.model_validate(parsed_payload)
                usage = payload.get("usage", {})
                duration_ms = int((time.perf_counter() - started_at) * 1000)
                return StructuredLLMResult(
                    parsed=parsed,
                    metadata={
                        "provider": "deepseek",
                        "model": model,
                        "status": "completed",
                        "duration_ms": duration_ms,
                        "retry_count": attempt - 1,
                        "input_summary": OpenAILLMClient._truncate(user_prompt),
                        "output_summary": OpenAILLMClient._truncate(output_text),
                        "fallback_used": False,
                        "error_type": None,
                        "usage": {
                            "input_tokens": usage.get("prompt_tokens"),
                            "output_tokens": usage.get("completion_tokens"),
                            "total_tokens": usage.get("total_tokens"),
                        },
                    },
                )
            except (httpx.HTTPError, json.JSONDecodeError, LLMClientError) as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                self.sleep_fn(float(attempt))

        raise LLMClientError(str(last_error) if last_error is not None else "LLM call failed.")

    @staticmethod
    def _normalize_payload(payload: dict, response_model: type[T] | None = None) -> dict:
        normalized = dict(payload)
        model_name = getattr(response_model, "__name__", "")

        if model_name == "ThesisDraftOutput":
            normalized = DeepSeekLLMClient._normalize_thesis_payload(normalized)

        if "company_one_liner" not in normalized:
            for alias in ("assessment", "summary", "one_liner", "investment_thesis"):
                value = normalized.get(alias)
                if isinstance(value, str) and value.strip():
                    normalized["company_one_liner"] = value
                    break
        for field_name in (
            "executive_summary",
            "base_case",
            "bear_case",
            "thesis_breakers",
            "uncertainties",
            "key_monitoring_items",
            "business_summary",
            "management_claims",
            "risk_factor_summary",
            "material_changes",
            "open_questions",
        ):
            value = normalized.get(field_name)
            if isinstance(value, str):
                normalized[field_name] = [value]
        confidence = normalized.get("confidence")
        if "decision_view" not in normalized:
            for alias in ("decision", "decision_summary", "stance", "action_view"):
                value = normalized.get(alias)
                if isinstance(value, str) and value.strip():
                    normalized["decision_view"] = value
                    break
        if isinstance(confidence, (int, float)):
            if confidence >= 75:
                normalized["confidence"] = "high"
            elif confidence >= 40:
                normalized["confidence"] = "medium"
            else:
                normalized["confidence"] = "low"
        elif isinstance(confidence, str):
            lowered = confidence.strip().lower()
            if lowered in {"low", "medium", "high"}:
                normalized["confidence"] = lowered
        return normalized

    @staticmethod
    def _normalize_thesis_payload(payload: dict) -> dict:
        normalized = dict(payload)
        bull_case = normalized.get("bull_case")
        bear_case = normalized.get("bear_case")
        thesis_breakers = normalized.get("thesis_breakers")
        thesis_breaker = normalized.get("thesis_breaker")

        if isinstance(bull_case, dict):
            core_argument = bull_case.get("core_argument")
            key_points = bull_case.get("key_points")
            actionable_implication = bull_case.get("actionable_implication")
            if isinstance(core_argument, str) and core_argument.strip() and "company_one_liner" not in normalized:
                normalized["company_one_liner"] = core_argument.strip()
            if isinstance(key_points, list) and "base_case" not in normalized:
                normalized["base_case"] = key_points
            if isinstance(actionable_implication, str) and actionable_implication.strip() and "decision_view" not in normalized:
                normalized["decision_view"] = actionable_implication.strip()
        elif isinstance(bull_case, str) and bull_case.strip():
            if "company_one_liner" not in normalized:
                normalized["company_one_liner"] = bull_case.strip()

        if isinstance(bear_case, dict):
            key_points = bear_case.get("key_points")
            core_argument = bear_case.get("core_argument")
            if isinstance(key_points, list):
                normalized["bear_case"] = key_points
            elif isinstance(core_argument, str) and core_argument.strip():
                normalized["bear_case"] = [core_argument.strip()]

        if isinstance(thesis_breakers, dict):
            bull_breakers = thesis_breakers.get("bull_thesis_breakers")
            bear_breakers = thesis_breakers.get("bear_thesis_breakers")
            if isinstance(bull_breakers, list) and bull_breakers:
                normalized["thesis_breakers"] = bull_breakers
            elif isinstance(bear_breakers, list) and bear_breakers:
                normalized["thesis_breakers"] = bear_breakers
        elif isinstance(thesis_breaker, str) and thesis_breaker.strip():
            normalized["thesis_breakers"] = [thesis_breaker.strip()]

        return normalized


def build_llm_client(settings) -> BaseLLMClient:
    if not settings.llm_enabled or not settings.openai_api_key:
        return NullLLMClient()
    if settings.llm_provider == "openai":
        return OpenAILLMClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    if settings.llm_provider == "deepseek":
        return DeepSeekLLMClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    raise LLMUnavailableError(f"Unsupported llm_provider: {settings.llm_provider}")
