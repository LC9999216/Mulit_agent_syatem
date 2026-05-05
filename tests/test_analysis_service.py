from app.constants import AnalysisStatus
from app.schemas.request import CompanyAnalysisRequest
from app.services.analysis_service import AnalysisService
from app.services.task_queue import InMemoryTaskQueue
from app.workers.tasks_analysis import AnalysisWorker


def test_analysis_service_persists_pending_job_until_worker_runs(isolated_service: AnalysisService) -> None:
    service = isolated_service
    request = CompanyAnalysisRequest(
        ticker="NVDA",
        user_goal="Assess whether the company merits continued tracking",
    )

    record = service.create_analysis(request)

    assert record.status == AnalysisStatus.PENDING
    assert service.get_status(record.request_id).status == AnalysisStatus.PENDING

    worker = AnalysisWorker(service.runtime_services, service.repository, service.queue)
    processed = worker.run_once()

    assert processed is True
    assert service.get_status(record.request_id).status == AnalysisStatus.COMPLETED
    report = service.get_report(record.request_id)
    assert report.ticker == "NVDA"


def test_worker_can_recover_pending_job_without_shared_queue(isolated_service: AnalysisService) -> None:
    service = isolated_service
    service.queue = InMemoryTaskQueue()
    request = CompanyAnalysisRequest(
        ticker="NVDA",
        user_goal="Assess whether the company merits continued tracking",
    )

    record = service.create_analysis(request)
    isolated_worker = AnalysisWorker(
        service.runtime_services,
        service.repository,
        InMemoryTaskQueue(),
    )

    processed = isolated_worker.run_once()

    assert processed is True
    assert service.get_status(record.request_id).status == AnalysisStatus.COMPLETED
