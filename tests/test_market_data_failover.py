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


class SuccessfulPolygonProvider:
    name = "polygon"

    def fetch_company_snapshot(self, ticker: str, on_retry=None) -> dict:
        return {
            "ticker": ticker,
            "price": 950.0,
            "price_change_1y": 0.82,
            "revenue_growth_yoy": 0.69,
            "gross_margin": 0.76,
            "source_uris": {"quote": f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"},
            "provider": self.name,
        }


def test_worker_records_provider_failover_and_succeeds_on_backup(isolated_service: AnalysisService) -> None:
    service = isolated_service
    service.runtime_services.market_data_client = MarketDataClient(
        use_demo_data=False,
        providers=[RateLimitedProvider(), SuccessfulPolygonProvider()],
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
    assert service.get_status(record.request_id).status == "completed"
    runs = service.list_agent_runs(record.request_id)
    provider_runs = [run for run in runs if run["stage_name"] == "fetch_provider"]
    assert provider_runs
    assert [run["payload"]["provider"] for run in provider_runs] == ["fmp", "fmp", "polygon", "polygon"]
    assert [run["status"] for run in provider_runs] == ["attempt", "failed", "attempt", "completed"]
    fetch_runs = [run for run in runs if run["stage_name"] == "fetch"]
    assert fetch_runs[-1]["status"] == "completed"
    assert fetch_runs[-1]["payload"]["market_snapshot"]["provider"] == "polygon"
