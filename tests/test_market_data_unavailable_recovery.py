from app.data_sources.market_data_client import MarketDataClient, MarketDataError, MarketDataRateLimitError
from app.schemas.request import CompanyAnalysisRequest
from app.services.analysis_service import AnalysisService
from app.workers.tasks_analysis import AnalysisWorker


class RateLimitedProvider:
    name = "fmp"

    def fetch_company_snapshot(self, ticker: str, on_retry=None) -> dict:
        raise MarketDataRateLimitError(
            message=f"FMP rate limited endpoint quote for {ticker}",
            source_uri=f"https://financialmodelingprep.com/stable/quote?symbol={ticker}",
            provider_name=self.name,
        )


class FailingProvider:
    def __init__(self, name: str) -> None:
        self.name = name

    def fetch_company_snapshot(self, ticker: str, on_retry=None) -> dict:
        raise MarketDataError(
            message=f"{self.name} unavailable for {ticker}",
            source_uri=f"https://example.com/{self.name}/{ticker}",
            provider_name=self.name,
        )


def test_worker_omits_zero_metrics_when_all_market_providers_fail(isolated_service: AnalysisService) -> None:
    service = isolated_service
    service.runtime_services.market_data_client = MarketDataClient(
        use_demo_data=False,
        providers=[RateLimitedProvider(), FailingProvider("polygon"), FailingProvider("finnhub")],
    )
    record = service.create_analysis(
        CompanyAnalysisRequest(
            ticker="NVDA",
            user_goal="Assess whether the company merits continued tracking",
        )
    )

    worker = AnalysisWorker(service.runtime_services, service.repository, service.queue)
    processed = worker.run_once()

    assert processed is True
    report = service.get_report(record.request_id)
    rendered_statements = [
        item.statement for item in [*report.facts, *report.bull_case, *report.bear_case]
    ]
    assert not any("0%" in statement for statement in rendered_statements)
    assert any("market data" in item.lower() for item in report.limitations)

    runs = service.list_agent_runs(record.request_id)
    fetch_runs = [run for run in runs if run["stage_name"] == "fetch"]
    assert fetch_runs[-1]["payload"]["market_snapshot"]["market_data_status"] == "unavailable"
