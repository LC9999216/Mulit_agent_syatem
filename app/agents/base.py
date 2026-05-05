from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    name: str

    def __init__(self, llm_client: object | None = None, llm_event_recorder=None, settings=None) -> None:
        self.llm_client = llm_client
        self.llm_event_recorder = llm_event_recorder
        self.settings = settings

    def _record_llm_call(self, request_id: str, status: str, payload: dict) -> None:
        if self.llm_event_recorder is not None:
            self.llm_event_recorder(request_id, status, payload)

    def _resolve_model_name(self, agent_name: str) -> str:
        if self.settings is None:
            return ""
        resolver = getattr(self.settings, "resolve_llm_model", None)
        if callable(resolver):
            return resolver(agent_name)
        return getattr(self.settings, f"llm_model_{agent_name}", "") or ""

    @abstractmethod
    def run(self, state: dict[str, Any]) -> Any:
        raise NotImplementedError
