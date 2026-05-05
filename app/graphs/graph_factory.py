import inspect
from typing import Literal

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.agents.registry import build_agent_registry
from app.constants import AnalysisStatus
from app.data_sources.market_data_client import MarketDataError, MarketDataRateLimitError
from app.schemas.state import GraphState
from app.services.report_service import ReportService
from app.services.runtime import RuntimeServices


def build_graph(runtime_services: RuntimeServices, stage_recorder=None):
    report_service = ReportService()

    def record_stage(state: GraphState, stage_name: str, payload: dict | None = None, status: str = "completed") -> None:
        if stage_recorder is None:
            return
        request_id = state.get("request_id")
        if request_id is None and payload is not None:
            request_id = payload.get("request_id")
        if request_id is None:
            return
        stage_recorder(request_id, stage_name, status, payload)

    agents = build_agent_registry(
        runtime_services=runtime_services,
        llm_event_recorder=lambda request_id, status, payload: stage_recorder(request_id, "llm_call", status, payload)
        if stage_recorder is not None
        else None,
    )

    def wrap_stage(stage_name: str, fn):
        def normalize(value):
            if isinstance(value, BaseModel):
                return value.model_dump(mode="json")
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            return value

        def wrapped(state: GraphState) -> dict:
            try:
                result = fn(state)
            except Exception as exc:
                record_stage(
                    state,
                    stage_name,
                    {"error": str(exc), "exception_type": exc.__class__.__name__},
                    status="failed",
                )
                raise
            safe_payload = normalize(result) if isinstance(result, dict) else {"value": str(result)}
            stage_status = safe_payload.pop("__stage_status", "completed") if isinstance(safe_payload, dict) else "completed"
            record_stage(state, stage_name, safe_payload, status=stage_status)
            return result

        return wrapped

    def init_node(state: GraphState) -> dict:
        request_id = state.get("request_id") or runtime_services.next_request_id()
        return {
            "request_id": request_id,
            "status": AnalysisStatus.RUNNING,
            "audit_log": [f"initialized:{request_id}"],
        }

    def fetch_node(state: GraphState) -> dict:
        request = state["request"]
        documents = runtime_services.sec_client.fetch_company_documents(request.ticker)
        news_events = runtime_services.news_client.fetch_company_news(request.ticker)
        audit_log = [*state.get("audit_log", []), "fetched:data"]
        limitations = [*state.get("limitations", [])]
        market_snapshot = {}
        stage_status = "completed"

        def on_market_retry(event: dict) -> None:
            record_stage(state, "fetch_retry", event, status="retrying")

        def on_provider_event(event: dict) -> None:
            record_stage(state, "fetch_provider", event, status=event["status"])

        try:
            fetch_company_snapshot = runtime_services.market_data_client.fetch_company_snapshot
            signature = inspect.signature(fetch_company_snapshot).parameters
            kwargs = {}
            if "on_retry" in signature:
                kwargs["on_retry"] = on_market_retry
            if "on_provider_event" in signature:
                kwargs["on_provider_event"] = on_provider_event
            market_snapshot = fetch_company_snapshot(request.ticker, **kwargs)
        except MarketDataRateLimitError as exc:
            stage_status = "failed"
            audit_log.append("fetch:market_data_rate_limited")
            limitations.append(
                "Market data was unavailable because the upstream provider rate-limited the request."
            )
            market_snapshot = {
                "ticker": request.ticker,
                "source_uris": {"quote": exc.source_uri},
                "market_data_status": "rate_limited",
                "market_data_error": str(exc),
            }
        except MarketDataError as exc:
            stage_status = "failed"
            audit_log.append("fetch:market_data_unavailable")
            limitations.append(
                "Market data was unavailable because all configured providers failed to return a usable snapshot."
            )
            market_snapshot = {
                "ticker": request.ticker,
                "source_uris": {"quote": exc.source_uri} if exc.source_uri else {},
                "market_data_status": "unavailable",
                "market_data_error": str(exc),
                "provider": exc.provider_name,
            }
        return {
            "documents": documents,
            "news_events": news_events,
            "market_snapshot": market_snapshot,
            "audit_log": audit_log,
            "limitations": limitations,
            "__stage_status": stage_status,
        }

    def supervisor_node(state: GraphState) -> dict:
        return {"supervisor_output": agents["supervisor"].run(state)}

    def filings_node(state: GraphState) -> dict:
        return {"filings_output": agents["filings"].run(state)}

    def financials_node(state: GraphState) -> dict:
        return {"financials_output": agents["financials"].run(state)}

    def market_node(state: GraphState) -> dict:
        return {"market_output": agents["market"].run(state)}

    def news_node(state: GraphState) -> dict:
        return {"news_output": agents["news"].run(state)}

    def thesis_node(state: GraphState) -> dict:
        return {"draft_report": agents["thesis"].run(state)}

    def validation_node(state: GraphState) -> dict:
        return {"validation_result": agents["validation"].run(state)}

    def repair_node(state: GraphState) -> dict:
        report = state["draft_report"]
        repaired = report.model_copy(
            update={
                "limitations": [
                    *report.limitations,
                    "Validation failed; unsupported statements were stripped from the output.",
                ],
                "facts": [item for item in report.facts if item.citations],
                "bull_case": [item for item in report.bull_case if item.citations],
                "bear_case": [item for item in report.bear_case if item.citations],
            }
        )
        return {"draft_report": repaired}

    def finalize_node(state: GraphState) -> dict:
        report = report_service.flatten_citations(state["draft_report"])
        return {
            "final_report": report,
            "status": AnalysisStatus.COMPLETED,
            "audit_log": [*state.get("audit_log", []), "finalized:report"],
        }

    def route_validation(state: GraphState) -> Literal["repair", "finalize"]:
        return "finalize" if state["validation_result"].passed else "repair"

    graph = StateGraph(GraphState)
    graph.add_node("init", wrap_stage("init", init_node))
    graph.add_node("fetch", wrap_stage("fetch", fetch_node))
    graph.add_node("supervisor", wrap_stage("supervisor", supervisor_node))
    graph.add_node("filings", wrap_stage("filings", filings_node))
    graph.add_node("financials", wrap_stage("financials", financials_node))
    graph.add_node("market", wrap_stage("market", market_node))
    graph.add_node("news", wrap_stage("news", news_node))
    graph.add_node("thesis", wrap_stage("thesis", thesis_node))
    graph.add_node("validate", wrap_stage("validate", validation_node))
    graph.add_node("repair", wrap_stage("repair", repair_node))
    graph.add_node("finalize", wrap_stage("finalize", finalize_node))
    graph.add_edge(START, "init")
    graph.add_edge("init", "fetch")
    graph.add_edge("fetch", "supervisor")
    graph.add_edge("supervisor", "filings")
    graph.add_edge("filings", "financials")
    graph.add_edge("financials", "market")
    graph.add_edge("market", "news")
    graph.add_edge("news", "thesis")
    graph.add_edge("thesis", "validate")
    graph.add_conditional_edges("validate", route_validation)
    graph.add_edge("repair", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()
