from typing import TypedDict

from app.schemas.filings import FilingsOutput
from app.schemas.financials import FinancialsOutput
from app.schemas.market import MarketOutput
from app.schemas.news import NewsOutput
from app.schemas.report import FinalReport
from app.schemas.request import CompanyAnalysisRequest
from app.schemas.validation import ValidationResult


class GraphState(TypedDict, total=False):
    request: CompanyAnalysisRequest
    request_id: str
    status: str
    audit_log: list[str]
    limitations: list[str]
    documents: list[dict]
    market_snapshot: dict
    news_events: list[dict]
    supervisor_output: dict
    filings_output: FilingsOutput
    financials_output: FinancialsOutput
    market_output: MarketOutput
    news_output: NewsOutput
    draft_report: FinalReport
    validation_result: ValidationResult
    final_report: FinalReport
