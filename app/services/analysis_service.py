from app.constants import AnalysisStatus
from app.graphs.graph_factory import build_graph
from app.schemas.report import FinalReport
from app.schemas.request import CompanyAnalysisRequest
from app.services.report_service import ReportService
from app.services.task_queue import InMemoryTaskQueue, RedisTaskQueue, TaskQueue
from app.services.runtime import RuntimeServices
from app.storage.db import build_session_factory
from app.storage.repositories.agent_runs import AgentRunRepository
from app.storage.repositories.analysis_requests import AnalysisRequestRepository, StoredAnalysisRequest


class AnalysisService:
    def __init__(
        self,
        runtime_services: RuntimeServices | None = None,
        repository: AnalysisRequestRepository | None = None,
        queue: TaskQueue | None = None,
    ) -> None:
        self.runtime_services = runtime_services or RuntimeServices()
        self.report_service = ReportService()
        session_factory = build_session_factory(self.runtime_services.settings.database_url)
        self.repository = repository or AnalysisRequestRepository(session_factory)
        self.agent_run_repository = AgentRunRepository(session_factory)
        setattr(self.repository, "agent_run_repository", self.agent_run_repository)
        self.queue = queue or self._build_queue()

    def create_analysis(self, request: CompanyAnalysisRequest) -> StoredAnalysisRequest:
        request_id = self.runtime_services.next_request_id()
        record = self.repository.create(
            request_id=request_id,
            ticker=request.ticker,
            status=AnalysisStatus.RUNNING,
            request_payload=request.model_dump(mode="json"),
        )
        pending_record = self.repository.update_status(request_id, AnalysisStatus.PENDING)
        self.queue.enqueue(request_id)
        return pending_record

    def get_status(self, request_id: str) -> StoredAnalysisRequest:
        record = self.repository.get(request_id)
        if record is None:
            raise KeyError(request_id)
        return record

    def get_report(self, request_id: str) -> FinalReport:
        record = self.get_status(request_id)
        if record.report_payload is None:
            raise KeyError(request_id)
        return FinalReport.model_validate(record.report_payload)

    def export_report_markdown(self, request_id: str, output_dir: str = "reports") -> tuple[str, str]:
        report = self.get_report(request_id)
        output_path = self.report_service.export_markdown(report, output_dir)
        markdown = output_path.read_text(encoding="utf-8")
        return str(output_path.resolve()), markdown

    def list_agent_runs(self, request_id: str) -> list[dict]:
        record = self.get_status(request_id)
        _ = record
        runs = self.agent_run_repository.list_for_request(request_id)
        return [
            {
                "id": run.id,
                "request_id": run.request_id,
                "stage_name": run.stage_name,
                "status": run.status,
                "payload": run.payload,
            }
            for run in runs
        ]

    def _build_queue(self) -> TaskQueue:
        redis_url = self.runtime_services.settings.redis_url
        try:
            queue = RedisTaskQueue(redis_url)
            queue.client.ping()
            return queue
        except Exception:
            return InMemoryTaskQueue()
