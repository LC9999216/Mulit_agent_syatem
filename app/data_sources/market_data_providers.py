from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import urlencode
import time

import httpx


class MarketDataError(Exception):
    def __init__(
        self,
        message: str,
        source_uri: str | None = None,
        provider_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.source_uri = source_uri
        self.provider_name = provider_name


class MarketDataRateLimitError(MarketDataError):
    pass


class FMPProvider:
    name = "fmp"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        http_client: httpx.Client | None = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
        sleep_fn=None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(base_url=self.base_url, timeout=20.0)
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep_fn = sleep_fn or time.sleep

    def fetch_company_snapshot(self, ticker: str, on_retry=None) -> dict:
        quote = self._get_first_record("quote", ticker, on_retry=on_retry)
        price_change = self._get_first_record("stock-price-change", ticker, on_retry=on_retry)
        income_growth = self._get_first_record("income-statement-growth", ticker, on_retry=on_retry)
        income_statement = self._get_first_record("income-statement", ticker, on_retry=on_retry)
        ratios = self._get_first_record("ratios", ticker, on_retry=on_retry)
        cash_flow = self._get_first_record("cash-flow-statement", ticker, on_retry=on_retry)

        revenue = self._safe_float(income_statement.get("revenue"))
        free_cash_flow = self._safe_float(cash_flow.get("freeCashFlow"))
        fcf_margin = free_cash_flow / revenue if revenue else 0.0

        return {
            "ticker": ticker,
            "price": self._safe_float(quote.get("price")),
            "year_high": self._safe_optional_float(quote.get("yearHigh")),
            "year_low": self._safe_optional_float(quote.get("yearLow")),
            "price_change_1y": self._safe_percent(price_change.get("1Y")),
            "revenue_growth_yoy": self._safe_percent(income_growth.get("growthRevenue")),
            "gross_margin": self._safe_percent(ratios.get("grossProfitMargin")),
            "fcf_margin": fcf_margin,
            "pe_ttm": self._first_optional_float(ratios, ["priceEarningsRatio", "priceEarningsRatioTTM", "peRatio"]),
            "price_to_sales": self._first_optional_float(ratios, ["priceToSalesRatio", "priceToSalesRatioTTM"]),
            "source_uris": {
                "quote": self._build_source_uri("quote", ticker),
                "price_change": self._build_source_uri("stock-price-change", ticker),
                "income_growth": self._build_source_uri("income-statement-growth", ticker),
                "income_statement": self._build_source_uri("income-statement", ticker),
                "ratios": self._build_source_uri("ratios", ticker),
                "cash_flow": self._build_source_uri("cash-flow-statement", ticker),
            },
            "provider": self.name,
        }

    def _get_first_record(self, endpoint: str, ticker: str, on_retry=None) -> dict:
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                response = self.http_client.get(
                    f"/{endpoint}",
                    params={"symbol": ticker, "apikey": self.api_key},
                )
                if response.status_code == 429:
                    raise MarketDataRateLimitError(
                        message=f"FMP rate limited endpoint {endpoint} for {ticker}",
                        source_uri=self._build_source_uri(endpoint, ticker),
                        provider_name=self.name,
                    )
                response.raise_for_status()
                payload = response.json()
                if not payload:
                    return {}
                if isinstance(payload, list):
                    return payload[0]
                if isinstance(payload, dict):
                    return payload
                return {}
            except (MarketDataRateLimitError, httpx.TransportError) as exc:
                if attempt >= attempts:
                    raise exc
                if on_retry is not None:
                    on_retry(
                        {
                            "ticker": ticker,
                            "provider": self.name,
                            "endpoint": endpoint,
                            "attempt": attempt,
                            "max_attempts": attempts,
                            "backoff_seconds": self.retry_backoff_seconds * attempt,
                            "reason": self._retry_reason(exc),
                        }
                    )
                self.sleep_fn(self.retry_backoff_seconds * attempt)
            except httpx.HTTPStatusError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    if attempt >= attempts:
                        raise MarketDataRateLimitError(
                            message=f"FMP rate limited endpoint {endpoint} for {ticker}",
                            source_uri=self._build_source_uri(endpoint, ticker),
                            provider_name=self.name,
                        ) from exc
                    if on_retry is not None:
                        on_retry(
                            {
                                "ticker": ticker,
                                "provider": self.name,
                                "endpoint": endpoint,
                                "attempt": attempt,
                                "max_attempts": attempts,
                                "backoff_seconds": self.retry_backoff_seconds * attempt,
                                "reason": "rate_limited",
                            }
                        )
                    self.sleep_fn(self.retry_backoff_seconds * attempt)
                    continue
                raise MarketDataError(
                    message=f"FMP request failed for endpoint {endpoint} and ticker {ticker}",
                    source_uri=self._build_source_uri(endpoint, ticker),
                    provider_name=self.name,
                ) from exc
        return {}

    def _build_source_uri(self, endpoint: str, ticker: str) -> str:
        return f"{self.base_url}/{endpoint}?{urlencode({'symbol': ticker})}"

    @staticmethod
    def _retry_reason(exc: Exception) -> str:
        if isinstance(exc, MarketDataRateLimitError):
            return "rate_limited"
        if isinstance(exc, httpx.TransportError):
            return "transport_error"
        return "retryable_error"

    @staticmethod
    def _safe_float(value: object) -> float:
        if value is None:
            return 0.0
        return float(value)

    @staticmethod
    def _safe_optional_float(value: object) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    @classmethod
    def _first_optional_float(cls, payload: dict, keys: list[str]) -> float | None:
        for key in keys:
            if payload.get(key) not in (None, ""):
                return cls._safe_optional_float(payload.get(key))
        return None

    @classmethod
    def _safe_percent(cls, value: object) -> float:
        number = cls._safe_float(value)
        if number > 1:
            return number / 100.0
        return number


class PolygonProvider:
    name = "polygon"

    def __init__(self, *, api_key: str, base_url: str, http_client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(base_url=self.base_url, timeout=20.0)

    def fetch_company_snapshot(self, ticker: str, on_retry=None) -> dict:
        prev_close = self._get_json(f"/v2/aggs/ticker/{ticker}/prev", params={"adjusted": "true"})
        financials = self._get_json("/vX/reference/financials", params={"ticker": ticker, "limit": 2, "order": "desc"})

        prev_results = prev_close.get("results") or []
        prev_item = prev_results[0] if prev_results else {}
        financial_results = financials.get("results") or []
        if len(financial_results) < 2:
            raise MarketDataError(
                message=f"Polygon returned insufficient financial history for {ticker}",
                source_uri=f"{self.base_url}/vX/reference/financials?ticker={ticker}",
                provider_name=self.name,
            )
        latest_financial = financial_results[0]
        previous_financial = financial_results[1]
        latest_income = (latest_financial.get("financials") or {}).get("income_statement") or {}
        previous_income = (previous_financial.get("financials") or {}).get("income_statement") or {}
        latest_cashflow = (latest_financial.get("financials") or {}).get("cash_flow_statement") or {}
        latest_revenue = self._statement_number(latest_income, ["revenues"])
        previous_revenue = self._statement_number(previous_income, ["revenues"])
        if latest_revenue is None or previous_revenue in (None, 0):
            raise MarketDataError(
                message=f"Polygon returned incomplete revenue data for {ticker}",
                source_uri=f"{self.base_url}/vX/reference/financials?ticker={ticker}",
                provider_name=self.name,
            )
        gross_profit = self._statement_number(latest_income, ["gross_profit"])
        cfo = self._statement_number(
            latest_cashflow,
            ["net_cash_flow_from_operating_activities", "net_cash_flow_from_operating_activities_continuing"],
        )
        gross_margin = (gross_profit / latest_revenue) if gross_profit is not None and latest_revenue else None
        fcf_margin = (cfo / latest_revenue) if cfo is not None and latest_revenue else None
        if prev_item.get("c") is None:
            raise MarketDataError(
                message=f"Polygon returned incomplete snapshot metrics for {ticker}",
                source_uri=f"{self.base_url}/v2/aggs/ticker/{ticker}/prev",
                provider_name=self.name,
            )

        revenue_growth = (latest_revenue - previous_revenue) / previous_revenue
        current_close = float(prev_item["c"])
        price_change_1y = self._compute_price_change_1y(ticker, current_close)
        return {
            "ticker": ticker,
            "price": current_close,
            "year_high": None,
            "year_low": None,
            "price_change_1y": price_change_1y,
            "revenue_growth_yoy": revenue_growth,
            "gross_margin": self._safe_percent(gross_margin) if gross_margin is not None else None,
            "fcf_margin": fcf_margin,
            "pe_ttm": None,
            "price_to_sales": None,
            "source_uris": {
                "quote": f"{self.base_url}/v2/aggs/ticker/{ticker}/prev",
                "price_change": f"{self.base_url}/v2/aggs/ticker/{ticker}/range/1/day",
                "income_statement": f"{self.base_url}/vX/reference/financials?ticker={ticker}",
                "ratios": f"{self.base_url}/vX/reference/financials?ticker={ticker}",
                "cash_flow": f"{self.base_url}/vX/reference/financials?ticker={ticker}",
            },
            "provider": self.name,
        }

    def _compute_price_change_1y(self, ticker: str, current_close: float) -> float:
        start = (date.today() - timedelta(days=370)).isoformat()
        end = date.today().isoformat()
        response = self._get_json(
            f"/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}",
            params={"adjusted": "true", "sort": "asc", "limit": 5000},
        )
        results = response.get("results") or []
        if not results or results[0].get("c") in (None, 0):
            raise MarketDataError(
                message=f"Polygon returned insufficient aggregate history for {ticker}",
                source_uri=f"{self.base_url}/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}",
                provider_name=self.name,
            )
        return (float(current_close) - float(results[0]["c"])) / float(results[0]["c"])

    def _get_json(self, path: str, params: dict | None = None) -> dict:
        response = self.http_client.get(path, params={**(params or {}), "apiKey": self.api_key})
        if response.status_code == 429:
            raise MarketDataRateLimitError(
                message=f"Polygon rate limited request for {path}",
                source_uri=f"{self.base_url}{path}",
                provider_name=self.name,
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MarketDataError(
                message=f"Polygon request failed for {path}",
                source_uri=f"{self.base_url}{path}",
                provider_name=self.name,
            ) from exc
        return response.json()

    @staticmethod
    def _statement_number(statement_payload: dict, keys: list[str]) -> float | None:
        for key in keys:
            entry = statement_payload.get(key)
            if isinstance(entry, dict) and entry.get("value") is not None:
                return float(entry["value"])
        return None

    @staticmethod
    def _safe_percent(value: object) -> float:
        number = float(value)
        if number > 1:
            return number / 100.0
        return number


class FinnhubProvider:
    name = "finnhub"

    def __init__(self, *, api_key: str, base_url: str, http_client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(base_url=self.base_url, timeout=20.0)

    def fetch_company_snapshot(self, ticker: str, on_retry=None) -> dict:
        quote = self._get_json("/quote", {"symbol": ticker})
        basic = self._get_json("/stock/metric", {"symbol": ticker, "metric": "all"})
        financials = self._get_json("/stock/financials-reported", {"symbol": ticker})

        metrics = basic.get("metric") or {}
        reports = financials.get("data") or []
        if len(reports) < 2:
            raise MarketDataError(
                message=f"Finnhub returned insufficient financial history for {ticker}",
                source_uri=f"{self.base_url}/stock/financials-reported?symbol={ticker}",
                provider_name=self.name,
            )
        latest_report = reports[0].get("report") or {}
        previous_report = reports[1].get("report") or {}
        latest_revenue = self._find_concept_value(
            latest_report.get("ic"),
            {
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "SalesRevenueNet",
                "us-gaap_Revenues",
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                "us-gaap_SalesRevenueNet",
            },
        )
        previous_revenue = self._find_concept_value(
            previous_report.get("ic"),
            {
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "SalesRevenueNet",
                "us-gaap_Revenues",
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                "us-gaap_SalesRevenueNet",
            },
        )
        cfo = self._find_concept_value(
            latest_report.get("cf"),
            {
                "NetCashProvidedByUsedInOperatingActivities",
                "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
                "us-gaap_NetCashProvidedByUsedInOperatingActivities",
                "us-gaap_NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
            },
        )
        capex = self._find_concept_value(
            latest_report.get("cf"),
            {
                "PaymentsToAcquirePropertyPlantAndEquipment",
                "CapitalExpenditures",
                "PaymentsToAcquireProductiveAssets",
                "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment",
                "us-gaap_PaymentsToAcquireProductiveAssets",
                "us-gaap_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
            },
        )
        gross_margin = metrics.get("grossMarginTTM")
        if gross_margin is None:
            gross_profit = self._find_concept_value(
                latest_report.get("ic"),
                {"GrossProfit", "us-gaap_GrossProfit"},
            )
            if gross_profit is not None and latest_revenue not in (None, 0):
                gross_margin = gross_profit / latest_revenue

        if latest_revenue is None or previous_revenue in (None, 0):
            raise MarketDataError(
                message=f"Finnhub returned incomplete revenue history for {ticker}",
                source_uri=f"{self.base_url}/stock/financials-reported?symbol={ticker}",
                provider_name=self.name,
            )
        if cfo is None and gross_margin is None:
            raise MarketDataError(
                message=f"Finnhub returned insufficient profitability metrics for {ticker}",
                source_uri=f"{self.base_url}/stock/financials-reported?symbol={ticker}",
                provider_name=self.name,
            )

        fcf_margin = None
        if cfo is not None:
            fcf_margin = ((cfo - abs(capex)) / latest_revenue) if capex is not None else (cfo / latest_revenue)

        price = quote.get("c")
        if price is None:
            raise MarketDataError(
                message=f"Finnhub returned incomplete quote data for {ticker}",
                source_uri=f"{self.base_url}/quote?symbol={ticker}",
                provider_name=self.name,
            )

        return {
            "ticker": ticker,
            "price": float(price),
            "year_high": self._safe_optional_float(metrics.get("52WeekHigh")),
            "year_low": self._safe_optional_float(metrics.get("52WeekLow")),
            "price_change_1y": self._safe_percent(metrics.get("52WeekPriceReturnDaily")),
            "revenue_growth_yoy": (latest_revenue - previous_revenue) / previous_revenue,
            "gross_margin": self._safe_percent(gross_margin) if gross_margin is not None else None,
            "fcf_margin": fcf_margin,
            "pe_ttm": self._safe_optional_float(metrics.get("peTTM")),
            "price_to_sales": self._safe_optional_float(metrics.get("psTTM")),
            "source_uris": {
                "quote": f"{self.base_url}/quote?symbol={ticker}",
                "price_change": f"{self.base_url}/stock/metric?symbol={ticker}&metric=all",
                "income_statement": f"{self.base_url}/stock/financials-reported?symbol={ticker}",
                "ratios": f"{self.base_url}/stock/metric?symbol={ticker}&metric=all",
                "cash_flow": f"{self.base_url}/stock/financials-reported?symbol={ticker}",
            },
            "provider": self.name,
        }

    def _get_json(self, path: str, params: dict) -> dict:
        response = self.http_client.get(path, params={**params, "token": self.api_key})
        if response.status_code == 429:
            raise MarketDataRateLimitError(
                message=f"Finnhub rate limited request for {path}",
                source_uri=f"{self.base_url}{path}",
                provider_name=self.name,
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MarketDataError(
                message=f"Finnhub request failed for {path}",
                source_uri=f"{self.base_url}{path}",
                provider_name=self.name,
            ) from exc
        return response.json()

    @staticmethod
    def _find_concept_value(items: list[dict] | None, concepts: set[str]) -> float | None:
        if not items:
            return None
        for item in items:
            concept = item.get("concept")
            if concept in concepts and item.get("value") is not None:
                return float(item["value"])
        return None

    @staticmethod
    def _safe_percent(value: object) -> float | None:
        if value is None:
            return None
        number = float(value)
        if number > 1:
            return number / 100.0
        return number

    @staticmethod
    def _safe_optional_float(value: object) -> float | None:
        if value in (None, ""):
            return None
        return float(value)
