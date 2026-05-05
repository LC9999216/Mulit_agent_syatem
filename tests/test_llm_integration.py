from types import SimpleNamespace

from app.schemas.request import CompanyAnalysisRequest
from app.services.analysis_service import AnalysisService
from app.workers.tasks_analysis import AnalysisWorker


class SuccessfulLLMClient:
    def generate_structured(self, *, agent_name, model, system_prompt, user_prompt, response_model):
        payloads = {
            "supervisor": {
                "execution_plan": [
                    "init",
                    "fetch_data",
                    "run_filings_agent",
                    "run_financials_agent",
                    "run_thesis_agent",
                    "run_validation_agent",
                    "finalize",
                ],
                "required_agents": ["filings", "financials", "thesis", "validation"],
                "blocking_conditions": [],
                "focus_areas": ["AI demand durability", "margin sustainability"],
            },
            "filings": {
                "business_summary": ["LLM filings summary: sustained AI infrastructure demand remains visible in SEC disclosures."],
                "management_claims": ["LLM filings summary: management tied growth to data center demand."],
                "risk_factor_summary": ["LLM filings summary: concentration and execution risks remain relevant."],
                "material_changes": ["LLM filings summary: recent filings highlighted current-period operating momentum."],
                "open_questions": ["What evidence in the next filing would confirm demand durability?"],
            },
            "thesis": {
                "company_one_liner": "NVDA remains a core AI infrastructure platform with strong disclosed demand.",
                "executive_summary": [
                    "LLM summary: disclosed demand and financial momentum support continued tracking.",
                    "LLM summary: limitations remain explicit and evidence-bound.",
                ],
                "uncertainties": ["Customer concentration and AI capex durability remain key unknowns."],
                "key_monitoring_items": ["Data center revenue growth", "Gross margin durability"],
                "confidence": "medium",
            },
            "validation": {
                "errors": [],
                "warnings": [
                    {
                        "path": "llm_review",
                        "message": "LLM review recommends keeping the evidence-bound wording.",
                        "severity": "warning",
                    }
                ],
            },
        }
        return SimpleNamespace(
            parsed=response_model.model_validate(payloads[agent_name]),
            metadata={
                "provider": "openai",
                "model": model,
                "status": "completed",
                "duration_ms": 25,
                "retry_count": 0,
                "input_summary": agent_name,
                "output_summary": f"{agent_name}:ok",
                "fallback_used": False,
                "error_type": None,
            },
        )


class FailingLLMClient:
    def generate_structured(self, *, agent_name, model, system_prompt, user_prompt, response_model):
        raise RuntimeError(f"{agent_name} llm failed")


def test_worker_records_llm_calls_and_uses_llm_outputs(isolated_service: AnalysisService) -> None:
    service = isolated_service
    service.runtime_services.settings.llm_enabled = True
    service.runtime_services.settings.openai_api_key = "test-key"
    service.runtime_services.llm_client = SuccessfulLLMClient()

    record = service.create_analysis(
        CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        )
    )

    worker = AnalysisWorker(service.runtime_services, service.repository, service.queue)
    worker.run_once()

    report = service.get_report(record.request_id)
    assert report.company_one_liner.startswith("NVDA remains a core AI infrastructure")
    assert report.executive_summary[0].startswith("LLM summary")

    runs = service.list_agent_runs(record.request_id)
    llm_runs = [run for run in runs if run["stage_name"] == "llm_call"]
    assert {run["payload"]["agent_name"] for run in llm_runs} >= {"supervisor", "thesis", "validation"}
    assert all(run["status"] == "completed" for run in llm_runs)

    validate_runs = [run for run in runs if run["stage_name"] == "validate"]
    assert validate_runs
    assert validate_runs[-1]["payload"]["validation_result"]["warnings"]


def test_worker_falls_back_to_rule_agents_when_llm_call_fails(isolated_service: AnalysisService) -> None:
    service = isolated_service
    service.runtime_services.settings.llm_enabled = True
    service.runtime_services.settings.openai_api_key = "test-key"
    service.runtime_services.llm_client = FailingLLMClient()

    record = service.create_analysis(
        CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        )
    )

    worker = AnalysisWorker(service.runtime_services, service.repository, service.queue)
    worker.run_once()

    status = service.get_status(record.request_id)
    assert status.status == "completed"

    report = service.get_report(record.request_id)
    assert report.executive_summary
    assert report.company_one_liner
    assert report.uncertainties
    assert report.key_monitoring_items

    runs = service.list_agent_runs(record.request_id)
    llm_runs = [run for run in runs if run["stage_name"] == "llm_call"]
    assert llm_runs
    assert all(run["status"] == "fallback" for run in llm_runs)
    assert all(run["payload"]["fallback_used"] is True for run in llm_runs)
