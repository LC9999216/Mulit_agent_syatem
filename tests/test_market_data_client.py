import httpx

from app.data_sources.market_data_client import MarketDataClient, MarketDataError, MarketDataRateLimitError


def test_market_data_client_maps_fmp_payloads_to_snapshot() -> None:
    responses = {
        "quote": [
            {
                "symbol": "NVDA",
                "price": 950.0,
                "yearHigh": 1000.0,
                "yearLow": 400.0,
            }
        ],
        "stock-price-change": [
            {
                "symbol": "NVDA",
                "1Y": 82.0,
            }
        ],
        "income-statement-growth": [
            {
                "symbol": "NVDA",
                "growthRevenue": 0.69,
            }
        ],
        "income-statement": [
            {
                "symbol": "NVDA",
                "revenue": 1000.0,
            }
        ],
        "ratios": [
            {
                "symbol": "NVDA",
                "grossProfitMargin": 0.76,
                "priceEarningsRatioTTM": 45.0,
                "priceToSalesRatioTTM": 22.0,
            }
        ],
        "cash-flow-statement": [
            {
                "symbol": "NVDA",
                "freeCashFlow": 490.0,
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        endpoint = request.url.path.rsplit("/", 1)[-1]
        payload = responses[endpoint]
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = MarketDataClient(
        api_key="test-key",
        use_demo_data=False,
        http_client=httpx.Client(transport=transport, base_url="https://financialmodelingprep.com"),
    )

    snapshot = client.fetch_company_snapshot("NVDA")

    assert snapshot["ticker"] == "NVDA"
    assert snapshot["price"] == 950.0
    assert snapshot["year_high"] == 1000.0
    assert snapshot["year_low"] == 400.0
    assert snapshot["price_change_1y"] == 0.82
    assert snapshot["revenue_growth_yoy"] == 0.69
    assert snapshot["gross_margin"] == 0.76
    assert snapshot["fcf_margin"] == 0.49
    assert snapshot["pe_ttm"] == 45.0
    assert snapshot["price_to_sales"] == 22.0
    assert snapshot["source_uris"]["quote"].endswith("/stable/quote?symbol=NVDA")
    assert snapshot["source_uris"]["income_statement"].endswith("/stable/income-statement?symbol=NVDA")


def test_market_data_client_retries_rate_limits_before_succeeding() -> None:
    attempts = {"quote": 0}
    sleep_calls: list[float] = []
    retry_events: list[dict] = []

    responses = {
        "stock-price-change": [{"symbol": "NVDA", "1Y": 82.0}],
        "income-statement-growth": [{"symbol": "NVDA", "growthRevenue": 0.69}],
        "income-statement": [{"symbol": "NVDA", "revenue": 1000.0}],
        "ratios": [{"symbol": "NVDA", "grossProfitMargin": 0.76}],
        "cash-flow-statement": [{"symbol": "NVDA", "freeCashFlow": 490.0}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        endpoint = request.url.path.rsplit("/", 1)[-1]
        if endpoint == "quote":
            attempts["quote"] += 1
            if attempts["quote"] < 3:
                return httpx.Response(429, json={"error": "rate limited"})
            return httpx.Response(200, json=[{"symbol": "NVDA", "price": 950.0}])
        return httpx.Response(200, json=responses[endpoint])

    transport = httpx.MockTransport(handler)
    client = MarketDataClient(
        api_key="test-key",
        use_demo_data=False,
        http_client=httpx.Client(transport=transport, base_url="https://financialmodelingprep.com"),
        max_retries=2,
        retry_backoff_seconds=0.5,
        sleep_fn=sleep_calls.append,
    )

    snapshot = client.fetch_company_snapshot("NVDA")

    assert snapshot["price"] == 950.0
    assert attempts["quote"] == 3
    assert sleep_calls == [0.5, 1.0]


def test_market_data_client_emits_retry_events() -> None:
    attempts = {"quote": 0}
    retry_events: list[dict] = []

    responses = {
        "stock-price-change": [{"symbol": "NVDA", "1Y": 82.0}],
        "income-statement-growth": [{"symbol": "NVDA", "growthRevenue": 0.69}],
        "income-statement": [{"symbol": "NVDA", "revenue": 1000.0}],
        "ratios": [{"symbol": "NVDA", "grossProfitMargin": 0.76}],
        "cash-flow-statement": [{"symbol": "NVDA", "freeCashFlow": 490.0}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        endpoint = request.url.path.rsplit("/", 1)[-1]
        if endpoint == "quote":
            attempts["quote"] += 1
            if attempts["quote"] < 3:
                return httpx.Response(429, json={"error": "rate limited"})
            return httpx.Response(200, json=[{"symbol": "NVDA", "price": 950.0}])
        return httpx.Response(200, json=responses[endpoint])

    transport = httpx.MockTransport(handler)
    client = MarketDataClient(
        api_key="test-key",
        use_demo_data=False,
        http_client=httpx.Client(transport=transport, base_url="https://financialmodelingprep.com"),
        max_retries=2,
        retry_backoff_seconds=0.5,
        sleep_fn=lambda seconds: None,
    )

    client.fetch_company_snapshot("NVDA", on_retry=retry_events.append)

    assert len(retry_events) == 2
    assert retry_events[0]["attempt"] == 1
    assert retry_events[0]["max_attempts"] == 3
    assert retry_events[0]["reason"] == "rate_limited"
    assert retry_events[1]["attempt"] == 2
    assert retry_events[1]["backoff_seconds"] == 1.0


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
            provider_name=self.name,
        )


class SuccessfulProvider:
    name = "finnhub"

    def fetch_company_snapshot(self, ticker: str, on_retry=None) -> dict:
        return {
            "ticker": ticker,
            "price": 950.0,
            "price_change_1y": 0.82,
            "revenue_growth_yoy": 0.69,
            "gross_margin": 0.76,
            "fcf_margin": 0.49,
            "source_uris": {"quote": f"https://finnhub.io/api/v1/quote?symbol={ticker}"},
            "provider": self.name,
        }


def test_market_data_client_fails_over_across_multiple_providers() -> None:
    provider_events: list[dict] = []
    client = MarketDataClient(
        use_demo_data=False,
        providers=[
            RateLimitedProvider(),
            FailingProvider("polygon"),
            SuccessfulProvider(),
        ],
    )

    snapshot = client.fetch_company_snapshot("NVDA", on_provider_event=provider_events.append)

    assert snapshot["provider"] == "finnhub"
    assert [event["provider"] for event in provider_events] == ["fmp", "fmp", "polygon", "polygon", "finnhub", "finnhub"]
    assert [event["status"] for event in provider_events] == ["attempt", "failed", "attempt", "failed", "attempt", "completed"]
