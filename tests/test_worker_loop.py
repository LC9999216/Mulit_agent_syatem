from app.constants import AnalysisStatus
from app.schemas.request import CompanyAnalysisRequest
from app.services.analysis_service import AnalysisService
from app.workers.tasks_analysis import AnalysisWorker


def test_worker_processes_multiple_jobs_until_queue_is_empty(isolated_service: AnalysisService) -> None:
    service = isolated_service
    first = service.create_analysis(
        CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        )
    )
    second = service.create_analysis(
        CompanyAnalysisRequest(
            ticker="AMD",
            user_goal="Assess whether the company merits continued tracking",
        )
    )

    worker = AnalysisWorker(service.runtime_services, service.repository, service.queue)
    processed = worker.run_until_empty(max_jobs=10)

    assert processed == 2
    assert service.get_status(first.request_id).status == AnalysisStatus.COMPLETED
    assert service.get_status(second.request_id).status == AnalysisStatus.COMPLETED
