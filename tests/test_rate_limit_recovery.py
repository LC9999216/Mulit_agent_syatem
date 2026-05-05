from app.data_sources.market_data_client import MarketDataRateLimitError
from app.schemas.request import CompanyAnalysisRequest
from app.services.analysis_service import AnalysisService
from app.workers.tasks_analysis import AnalysisWorker


class RateLimitedMarketClient:
    def fetch_company_snapshot(self, ticker: str, on_retry=None) -> dict:
        if on_retry is not None:
            on_retry(
                {
                    "ticker": ticker,
                    "endpoint": "quote",
                    "attempt": 1,
                    "max_attempts": 3,
                    "backoff_seconds": 1.0,
                    "reason": "rate_limited",
                }
            )
            on_retry(
                {
                    "ticker": ticker,
                    "endpoint": "quote",
                    "attempt": 2,
                    "max_attempts": 3,
                    "backoff_seconds": 2.0,
                    "reason": "rate_limited",
                }
            )
        raise MarketDataRateLimitError(
            message=f"FMP rate limited endpoint quote for {ticker}",
            source_uri=f"https://financialmodelingprep.com/stable/quote?symbol={ticker}",
        )


def test_worker_degrades_when_market_data_is_rate_limited(isolated_service: AnalysisService) -> None:
    service = isolated_service
    service.runtime_services.market_data_client = RateLimitedMarketClient()
    record = service.create_analysis(
        CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        )
    )

    worker = AnalysisWorker(service.runtime_services, service.repository, service.queue)

    processed = worker.run_once()

    assert processed is True
    status = service.get_status(record.request_id)
    assert status.status == "completed"
    report = service.get_report(record.request_id)
    assert any("market data" in item.lower() for item in report.limitations)
    rendered_statements = [
        item.statement for item in [*report.facts, *report.bull_case, *report.bear_case]
    ]
    assert not any("0%" in statement for statement in rendered_statements)
    runs = service.list_agent_runs(record.request_id)
    retry_runs = [run for run in runs if run["stage_name"] == "fetch_retry"]
    assert len(retry_runs) == 2
    assert retry_runs[0]["status"] == "retrying"
    assert retry_runs[0]["payload"]["attempt"] == 1
    assert retry_runs[1]["payload"]["attempt"] == 2
    fetch_runs = [run for run in runs if run["stage_name"] == "fetch"]
    assert fetch_runs
    assert fetch_runs[-1]["status"] == "failed"
    assert fetch_runs[-1]["payload"]["market_snapshot"]["market_data_status"] == "rate_limited"
