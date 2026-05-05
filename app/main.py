from fastapi import Depends, FastAPI, HTTPException

from app.schemas.request import CompanyAnalysisRequest
from app.services.analysis_service import AnalysisService
from app.services.runtime import RuntimeServices


def create_app(
    runtime_services: RuntimeServices | None = None,
    analysis_service: AnalysisService | None = None,
) -> FastAPI:
    app = FastAPI(title="Stock Research Multi-Agent")
    app.state.analysis_service = analysis_service or AnalysisService(runtime_services)

    def get_analysis_service() -> AnalysisService:
        return app.state.analysis_service

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/analyze/company", status_code=202)
    def analyze_company(
        request: CompanyAnalysisRequest,
        service: AnalysisService = Depends(get_analysis_service),
    ) -> dict[str, str]:
        record = service.create_analysis(request)
        return {"request_id": record.request_id, "status": record.status}

    @app.get("/analysis/{request_id}")
    def get_analysis(
        request_id: str,
        service: AnalysisService = Depends(get_analysis_service),
    ) -> dict:
        try:
            record = service.get_status(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="analysis not found") from exc
        return {
            "request_id": record.request_id,
            "status": record.status,
            "error_message": record.error_message,
            "has_report": record.report_payload is not None,
        }

    @app.get("/analysis/{request_id}/runs")
    def get_analysis_runs(
        request_id: str,
        service: AnalysisService = Depends(get_analysis_service),
    ) -> dict:
        try:
            runs = service.list_agent_runs(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="analysis not found") from exc
        return {"request_id": request_id, "runs": runs}

    @app.get("/report/{request_id}")
    def get_report(
        request_id: str,
        service: AnalysisService = Depends(get_analysis_service),
    ) -> dict:
        try:
            report = service.get_report(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="report not found") from exc
        return report.model_dump(mode="json")

    @app.get("/report/{request_id}/markdown")
    def get_report_markdown(
        request_id: str,
        service: AnalysisService = Depends(get_analysis_service),
    ) -> dict:
        try:
            path, markdown = service.export_report_markdown(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="report not found") from exc
        return {"request_id": request_id, "path": path, "markdown": markdown}

    return app
