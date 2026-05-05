import httpx

from app.config import get_settings
from app.data_sources.market_data_providers import (
    FMPProvider,
    FinnhubProvider,
    MarketDataError,
    MarketDataRateLimitError,
    PolygonProvider,
)


class MarketDataClient:
    def __init__(
        self,
        api_key: str | None = None,
        use_demo_data: bool | None = None,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        sleep_fn=None,
        providers: list[object] | None = None,
    ) -> None:
        settings = get_settings()
        self.use_demo_data = settings.use_demo_data if use_demo_data is None else use_demo_data
        self.providers = providers or self._build_providers(
            settings=settings,
            fmp_api_key=api_key or settings.market_data_api_key,
            fmp_base_url=base_url or settings.market_data_base_url,
            http_client=http_client,
            max_retries=settings.market_data_max_retries if max_retries is None else max_retries,
            retry_backoff_seconds=(
                settings.market_data_retry_backoff_seconds
                if retry_backoff_seconds is None
                else retry_backoff_seconds
            ),
            sleep_fn=sleep_fn,
        )

    def fetch_company_snapshot(self, ticker: str, on_retry=None, on_provider_event=None) -> dict:
        if self.use_demo_data or not self.providers:
            return {
                "ticker": ticker,
                "price": 950.0,
                "price_change_1y": 0.64,
                "revenue_growth_yoy": 0.58,
                "gross_margin": 0.74,
                "fcf_margin": 0.41,
                "source_uris": {
                    "quote": "demo://market/quote",
                    "price_change": "demo://market/price-change",
                    "income_growth": "demo://market/income-growth",
                    "ratios": "demo://market/ratios",
                    "cash_flow": "demo://market/cash-flow",
                },
                "provider": "demo",
            }

        last_error: MarketDataError | None = None
        for provider in self.providers:
            if on_provider_event is not None:
                on_provider_event({"provider": provider.name, "status": "attempt", "ticker": ticker})
            try:
                snapshot = provider.fetch_company_snapshot(ticker, on_retry=on_retry)
                snapshot.setdefault("provider", provider.name)
                if on_provider_event is not None:
                    on_provider_event({"provider": provider.name, "status": "completed", "ticker": ticker})
                return snapshot
            except MarketDataError as exc:
                last_error = exc
                if on_provider_event is not None:
                    on_provider_event(
                        {
                            "provider": provider.name,
                            "status": "failed",
                            "ticker": ticker,
                            "reason": str(exc),
                            "error_type": exc.__class__.__name__,
                        }
                    )
                continue

        if last_error is not None:
            raise last_error
        raise MarketDataError(f"No market data providers available for {ticker}")

    def _build_providers(
        self,
        *,
        settings,
        fmp_api_key: str,
        fmp_base_url: str,
        http_client: httpx.Client | None,
        max_retries: int,
        retry_backoff_seconds: float,
        sleep_fn,
    ) -> list[object]:
        provider_names = [
            item.strip().lower()
            for item in settings.market_data_providers.split(",")
            if item.strip()
        ]
        providers: list[object] = []
        for provider_name in provider_names:
            if provider_name == "fmp" and fmp_api_key:
                providers.append(
                    FMPProvider(
                        api_key=fmp_api_key,
                        base_url=fmp_base_url,
                        http_client=http_client,
                        max_retries=max_retries,
                        retry_backoff_seconds=retry_backoff_seconds,
                        sleep_fn=sleep_fn,
                    )
                )
            elif provider_name == "polygon" and settings.polygon_api_key:
                providers.append(
                    PolygonProvider(
                        api_key=settings.polygon_api_key,
                        base_url=settings.polygon_base_url,
                    )
                )
            elif provider_name == "finnhub" and settings.finnhub_api_key:
                providers.append(
                    FinnhubProvider(
                        api_key=settings.finnhub_api_key,
                        base_url=settings.finnhub_base_url,
                    )
                )
        return providers
