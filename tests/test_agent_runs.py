from app.schemas.request import CompanyAnalysisRequest
from app.services.analysis_service import AnalysisService
from app.workers.tasks_analysis import AnalysisWorker


def test_worker_persists_agent_run_audit_records(isolated_service: AnalysisService) -> None:
    service = isolated_service
    record = service.create_analysis(
        CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        )
    )

    worker = AnalysisWorker(service.runtime_services, service.repository, service.queue)
    worker.run_once()

    agent_runs = service.agent_run_repository.list_for_request(record.request_id)
    stages = [run.stage_name for run in agent_runs]

    assert "init" in stages
    assert "fetch" in stages
    assert "supervisor" in stages
    assert "filings" in stages
    assert "financials" in stages
    assert "thesis" in stages
    assert "validate" in stages
    assert "finalize" in stages
