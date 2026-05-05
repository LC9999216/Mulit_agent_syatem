from app.schemas.request import CompanyAnalysisRequest


class HermesAdapter:
    """Translate future Hermes payloads into internal request objects."""

    def from_http_payload(self, payload: dict) -> CompanyAnalysisRequest:
        return CompanyAnalysisRequest.model_validate(payload)

    def to_mcp_tool_payload(self, request: CompanyAnalysisRequest) -> dict:
        return {
            "tool": "analyze_company",
            "input": request.model_dump(mode="json"),
        }
