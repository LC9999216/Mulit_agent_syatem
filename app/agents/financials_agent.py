from app.agents.base import BaseAgent
from app.schemas.common import Citation, ConfidenceLevel, StatementWithCitations
from app.schemas.financials import FinancialsOutput, MetricPoint


class FinancialsAgent(BaseAgent):
    name = "financials"

    def run(self, state: dict) -> FinancialsOutput:
        snapshot = state.get("market_snapshot", {})
        ticker = state["request"].ticker
        source_uris = snapshot.get("source_uris", {})
        market_data_status = snapshot.get("market_data_status")
        if market_data_status in {"rate_limited", "unavailable"}:
            quote_citation = Citation(
                source_type="market_data",
                source_uri=source_uris.get("quote", f"market://snapshot/{ticker}/quote"),
                label=f"{ticker} quote endpoint",
                support_type="market_data",
            )
            if market_data_status == "rate_limited":
                anomaly_statement = (
                    f"Market data was unavailable because the upstream provider rate-limited the request, "
                    f"so quantitative financial conclusions were omitted for {ticker}."
                )
            else:
                anomaly_statement = (
                    f"Market data was unavailable because all configured providers failed to return a usable snapshot, "
                    f"so quantitative financial conclusions were omitted for {ticker}."
                )
            return FinancialsOutput(
                key_metrics_table={},
                trend_findings=[],
                quality_checks=[],
                anomalies=[
                    StatementWithCitations(
                        statement=anomaly_statement,
                        citations=[quote_citation],
                    )
                ],
                market_context=[],
                citations=[quote_citation],
                confidence=ConfidenceLevel.LOW,
            )

        growth_citation = Citation(
            source_type="market_data",
            source_uri=source_uris.get("income_growth", f"market://snapshot/{ticker}/income-growth"),
            label=f"{ticker} income statement growth",
            support_type="market_data",
        )
        ratios_citation = Citation(
            source_type="market_data",
            source_uri=source_uris.get("ratios", f"market://snapshot/{ticker}/ratios"),
            label=f"{ticker} ratios",
            support_type="market_data",
        )
        price_citation = Citation(
            source_type="market_data",
            source_uri=source_uris.get("price_change", f"market://snapshot/{ticker}/price-change"),
            label=f"{ticker} stock price change",
            support_type="market_data",
        )
        cash_flow_citation = Citation(
            source_type="market_data",
            source_uri=source_uris.get("cash_flow", f"market://snapshot/{ticker}/cash-flow"),
            label=f"{ticker} cash flow statement",
            support_type="market_data",
        )
        income_statement_citation = Citation(
            source_type="market_data",
            source_uri=source_uris.get("income_statement", f"market://snapshot/{ticker}/income-statement"),
            label=f"{ticker} income statement",
            support_type="market_data",
        )

        revenue_growth = snapshot.get("revenue_growth_yoy")
        gross_margin = snapshot.get("gross_margin")
        price_change = snapshot.get("price_change_1y")
        fcf_margin = snapshot.get("fcf_margin")

        key_metrics_table: dict[str, list[MetricPoint]] = {}
        trend_findings: list[StatementWithCitations] = []
        quality_checks: list[StatementWithCitations] = []
        market_context: list[StatementWithCitations] = []

        if revenue_growth is not None:
            key_metrics_table["revenue_growth_yoy"] = [
                MetricPoint(period="latest", value=revenue_growth, source="market_snapshot")
            ]
            trend_findings.append(
                StatementWithCitations(
                    statement=f"{ticker} revenue growth remains elevated at {revenue_growth:.0%}.",
                    citations=[growth_citation],
                )
            )
        if gross_margin is not None:
            key_metrics_table["gross_margin"] = [
                MetricPoint(period="latest", value=gross_margin, source="market_snapshot")
            ]
            quality_checks.append(
                StatementWithCitations(
                    statement=f"Gross margin remains strong at {gross_margin:.0%}.",
                    citations=[ratios_citation],
                )
            )
        if fcf_margin is not None:
            key_metrics_table["fcf_margin"] = [
                MetricPoint(period="latest", value=fcf_margin, source="market_snapshot")
            ]
            quality_checks.append(
                StatementWithCitations(
                    statement=f"Free cash flow margin is approximately {fcf_margin:.0%}.",
                    citations=[cash_flow_citation, income_statement_citation],
                )
            )
        if price_change is not None:
            market_context.append(
                StatementWithCitations(
                    statement=f"The stock is up {price_change:.0%} over the trailing year.",
                    citations=[price_citation],
                )
            )

        return FinancialsOutput(
            key_metrics_table=key_metrics_table,
            trend_findings=trend_findings,
            quality_checks=quality_checks,
            anomalies=[],
            market_context=market_context,
            citations=[
                growth_citation,
                ratios_citation,
                price_citation,
                cash_flow_citation,
                income_statement_citation,
            ],
            confidence=ConfidenceLevel.MEDIUM,
        )
