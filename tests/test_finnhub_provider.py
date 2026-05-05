import httpx
import pytest

from app.data_sources.market_data_providers import FinnhubProvider


def test_finnhub_provider_builds_snapshot_from_reported_financials_when_basic_metrics_are_partial() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/quote":
            return httpx.Response(200, json={"c": 201.36})
        if request.url.path == "/api/v1/stock/metric":
            return httpx.Response(
                200,
                json={
                    "metric": {
                        "52WeekPriceReturnDaily": 81.9,
                        "52WeekHigh": 220.0,
                        "52WeekLow": 90.0,
                        "peTTM": 41.5,
                        "psTTM": 23.2,
                    }
                },
            )
        if request.url.path == "/api/v1/stock/financials-reported":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "report": {
                                "ic": [
                                    {"concept": "us-gaap_Revenues", "value": 130497000000},
                                    {"concept": "GrossProfit", "value": 92798000000},
                                ],
                                "cf": [
                                    {
                                        "concept": "us-gaap_NetCashProvidedByUsedInOperatingActivities",
                                        "value": 62078000000,
                                    }
                                ],
                            }
                        },
                        {
                            "report": {
                                "ic": [{"concept": "us-gaap_Revenues", "value": 41172000000}],
                                "cf": [],
                            }
                        },
                    ]
                },
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    transport = httpx.MockTransport(handler)
    provider = FinnhubProvider(
        api_key="test-key",
        base_url="https://finnhub.io/api/v1",
        http_client=httpx.Client(transport=transport, base_url="https://finnhub.io/api/v1"),
    )

    snapshot = provider.fetch_company_snapshot("NVDA")

    assert snapshot["provider"] == "finnhub"
    assert snapshot["price"] == 201.36
    assert snapshot["price_change_1y"] == pytest.approx(0.819)
    assert snapshot["revenue_growth_yoy"] > 2.0
    assert snapshot["gross_margin"] > 0.7
    assert snapshot["fcf_margin"] > 0.4
    assert snapshot["year_high"] == 220.0
    assert snapshot["year_low"] == 90.0
    assert snapshot["pe_ttm"] == 41.5
    assert snapshot["price_to_sales"] == 23.2
