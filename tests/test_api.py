from fastapi.testclient import TestClient

from app.main import create_app
from app.services.analysis_service import AnalysisService
from app.workers.tasks_analysis import AnalysisWorker


def test_api_creates_analysis_enqueues_background_job(isolated_service: AnalysisService) -> None:
    service = isolated_service
    app = create_app(analysis_service=service)
    client = TestClient(app)

    create_response = client.post(
        "/analyze/company",
        json={
            "ticker": "NVDA",
            "user_goal": "Assess whether the company merits continued tracking",
        },
    )

    assert create_response.status_code == 202
    request_id = create_response.json()["request_id"]
    assert create_response.json()["status"] == "pending"

    status_response = client.get(f"/analysis/{request_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "pending"
    assert status_response.json()["error_message"] is None
    assert status_response.json()["has_report"] is False

    report_response = client.get(f"/report/{request_id}")
    assert report_response.status_code == 404


def test_api_returns_agent_run_audit_log(isolated_service: AnalysisService) -> None:
    service = isolated_service
    app = create_app(analysis_service=service)
    client = TestClient(app)

    create_response = client.post(
        "/analyze/company",
        json={
            "ticker": "NVDA",
            "user_goal": "Assess whether the company merits continued tracking",
        },
    )
    request_id = create_response.json()["request_id"]

    worker = AnalysisWorker(service.runtime_services, service.repository, service.queue)
    worker.agent_run_repository = service.agent_run_repository
    worker.run_once()

    runs_response = client.get(f"/analysis/{request_id}/runs")
    assert runs_response.status_code == 200
    body = runs_response.json()
    assert body["request_id"] == request_id
    assert body["runs"]
    assert body["runs"][0]["stage_name"] == "init"
    assert any(run["stage_name"] == "finalize" for run in body["runs"])

    status_response = client.get(f"/analysis/{request_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"
    assert status_response.json()["error_message"] is None
    assert status_response.json()["has_report"] is True


def test_api_exports_report_markdown_file(isolated_service: AnalysisService) -> None:
    service = isolated_service
    app = create_app(analysis_service=service)
    client = TestClient(app)

    create_response = client.post(
        "/analyze/company",
        json={
            "ticker": "NVDA",
            "user_goal": "Assess whether the company merits continued tracking",
        },
    )
    request_id = create_response.json()["request_id"]

    worker = AnalysisWorker(service.runtime_services, service.repository, service.queue)
    worker.agent_run_repository = service.agent_run_repository
    worker.run_once()

    markdown_response = client.get(f"/report/{request_id}/markdown")
    assert markdown_response.status_code == 200
    body = markdown_response.json()
    assert body["request_id"] == request_id
    assert body["path"].endswith(f"{request_id}.md")
    assert "# NVDA Research Report" in body["markdown"]
