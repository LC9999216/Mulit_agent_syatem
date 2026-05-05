from pathlib import Path
from uuid import uuid4

from app.schemas.common import Citation, StatementWithCitations
from app.schemas.report import FinalReport, TradePlan
from app.services.report_service import ReportService


def build_report() -> FinalReport:
    filing_citation = Citation(
        source_type="filing",
        source_uri="https://www.sec.gov/example",
        label="10-K 2026-02-25 / Business",
        doc_date="2026-02-25",
        section="Business",
        support_type="filing",
    )
    return FinalReport(
        request_id="req-test",
        ticker="NVDA",
        company_one_liner="NVDA remains a high-momentum AI infrastructure name.",
        executive_summary=[
            "Demand remains strong across data center workloads.",
            "Profitability and cash generation remain elevated.",
        ],
        what_happened=[
            "Recent filings and market data indicate NVDA remains a core AI infrastructure beneficiary."
        ],
        market_view=[
            "The stock is trading off a very strong trailing move, so the market already embeds elevated execution expectations."
        ],
        latest_price_analysis=[
            "NVDA is trading near the upper end of its 52-week range and above key moving averages.",
            "Nearest support sits near 50-day trend support while resistance is defined by the recent swing high.",
        ],
        price_action_summary=[
            "Shares remain near the upper end of their trailing range after a strong 12-month advance."
        ],
        valuation_view=[
            "Valuation should be treated as demanding when compared with a normalized growth path."
        ],
        recent_bullish_catalysts=[
            StatementWithCitations(
                statement="Recent disclosures continue to frame CUDA and AI infrastructure demand as durable tailwinds.",
                citations=[filing_citation],
            )
        ],
        recent_bearish_catalysts=[
            StatementWithCitations(
                statement="Export restrictions and customer concentration remain live downside catalysts.",
                citations=[filing_citation],
            )
        ],
        key_news_items=[
            StatementWithCitations(
                statement="Recent company and market coverage has remained focused on AI demand durability and regulatory risk.",
                citations=[filing_citation],
            )
        ],
        important_news=[
            StatementWithCitations(
                statement="An earnings-related 8-K and associated management commentary remain the most material recent disclosed event.",
                citations=[filing_citation],
            )
        ],
        bullish_factors=[
            StatementWithCitations(
                statement="Gross margin and free cash flow remain supportive of a premium operating profile.",
                citations=[filing_citation],
            )
        ],
        bearish_factors=[
            StatementWithCitations(
                statement="Valuation remains stretched enough that even moderate growth normalization could pressure the stock.",
                citations=[filing_citation],
            )
        ],
        base_case=[
            "Base case assumes AI infrastructure demand remains strong but normalizes from current extreme growth rates."
        ],
        facts=[
            StatementWithCitations(
                statement="NVIDIA described sustained demand for accelerated computing.",
                citations=[filing_citation],
            )
        ],
        bull_case=[],
        bear_case=[
            StatementWithCitations(
                statement="Customer concentration and export restrictions could pressure growth durability.",
                citations=[filing_citation],
            )
        ],
        decision_view="Continue tracking, but treat the name as execution-sensitive after a period of exceptional growth.",
        short_term_plan=TradePlan(
            horizon="short_term",
            bias="bullish",
            entry_context="Prefer pullbacks into support rather than chasing extension.",
            target_price=1125.0,
            stop_loss=980.0,
            position_size_pct=12.0,
            rationale=["Momentum remains strong, but extension argues for disciplined entries."],
            invalidators=["Loss of near-term support would invalidate the short-term setup."],
        ),
        mid_term_plan=TradePlan(
            horizon="mid_term",
            bias="bullish",
            entry_context="Use staged entries while the primary uptrend remains intact.",
            target_price=1250.0,
            stop_loss=920.0,
            position_size_pct=20.0,
            rationale=["Fundamentals remain strong enough to support an intermediate-term follow-through case."],
            invalidators=["A break of medium-term trend support would weaken the setup."],
        ),
        long_term_thesis=[
            "NVIDIA remains a leveraged beneficiary of sustained AI infrastructure spending and ecosystem lock-in."
        ],
        long_term_conditions=[
            "Data center demand must remain strong.",
            "Gross margin and free cash flow must stay structurally elevated.",
        ],
        thesis_breakers=["A material slowdown in data center demand would weaken the thesis."],
        uncertainties=["Customer concentration remains a monitoring point."],
        key_monitoring_items=["Gross margin trajectory"],
        citations=[filing_citation],
        confidence="medium",
        limitations=[],
    )


def test_report_service_renders_markdown_report() -> None:
    service = ReportService()

    markdown = service.render_markdown(build_report())

    assert "# NVDA Research Report" in markdown
    assert "## Executive Summary" in markdown
    assert "## Latest Price Analysis" in markdown
    assert "## Important News" in markdown
    assert "## Bullish Factors" in markdown
    assert "## Bearish Factors" in markdown
    assert "## Short-Term Plan" in markdown
    assert "## Mid-Term Plan" in markdown
    assert "## Long-Term Thesis" in markdown
    assert "## Long-Term Conditions" in markdown
    assert "## Base Case" in markdown
    assert "Demand remains strong across data center workloads." in markdown
    assert "## Decision View" in markdown
    assert "## Thesis Breakers" in markdown
    assert "## Facts" in markdown
    assert "NVIDIA described sustained demand for accelerated computing." in markdown
    assert "## Citations" in markdown
    assert "https://www.sec.gov/example" in markdown


def test_report_service_exports_markdown_file() -> None:
    service = ReportService()
    output_dir = Path.cwd() / f".test-reports-{uuid4().hex}"

    output_path = service.export_markdown(build_report(), output_dir)

    assert output_path.name == "req-test.md"
    assert output_path.exists()
    assert "NVDA Research Report" in output_path.read_text(encoding="utf-8")
