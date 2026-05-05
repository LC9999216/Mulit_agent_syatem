from app.constants import AnalysisStatus
from app.graphs.graph_factory import build_graph
from app.schemas.request import CompanyAnalysisRequest
from app.services.task_queue import TaskQueue
from app.services.runtime import RuntimeServices
from app.storage.repositories.analysis_requests import AnalysisRequestRepository


class AnalysisWorker:
    def __init__(
        self,
        runtime_services: RuntimeServices,
        repository: AnalysisRequestRepository,
        queue: TaskQueue,
    ) -> None:
        self.runtime_services = runtime_services
        self.repository = repository
        self.agent_run_repository = getattr(repository, "agent_run_repository", None)
        self.queue = queue
        self.graph = build_graph(runtime_services, self._record_stage)

    def run_once(self) -> bool:
        request_id = self.queue.dequeue()
        if request_id is None:
            record = self.repository.get_oldest_by_status(AnalysisStatus.PENDING)
            if record is None:
                return False
            request_id = record.request_id
        else:
            record = self.repository.get(request_id)
            if record is None:
                return False

        self.repository.update_status(request_id, AnalysisStatus.RUNNING)
        try:
            request = CompanyAnalysisRequest.model_validate(record.request_payload)
            result = self.graph.invoke({"request": request, "request_id": request_id})
            report = result["final_report"].model_dump(mode="json")
            self.repository.save_report(request_id, AnalysisStatus.COMPLETED, report)
        except Exception as exc:
            self.repository.update_status(request_id, AnalysisStatus.FAILED, error_message=str(exc))
            if self.agent_run_repository is not None:
                self.agent_run_repository.create(
                    request_id=request_id,
                    stage_name="worker",
                    status="failed",
                    payload={"error": str(exc), "exception_type": exc.__class__.__name__},
                )
        return True

    def run_until_empty(self, max_jobs: int = 100) -> int:
        processed = 0
        while processed < max_jobs:
            handled = self.run_once()
            if not handled:
                break
            processed += 1
        return processed

    def _record_stage(self, request_id: str, stage_name: str, status: str, payload: dict | None) -> None:
        if self.agent_run_repository is not None:
            self.agent_run_repository.create(
                request_id=request_id,
                stage_name=stage_name,
                status=status,
                payload=payload,
            )
