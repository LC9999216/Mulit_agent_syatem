from pydantic import BaseModel, Field

from app.schemas.common import Citation, ConfidenceLevel, StatementWithCitations
from app.schemas.market import TradePlan


class FinalReport(BaseModel):
    request_id: str
    ticker: str
    company_one_liner: str
    executive_summary: list[str] = Field(default_factory=list)
    what_happened: list[str] = Field(default_factory=list)
    market_view: list[str] = Field(default_factory=list)
    latest_price_analysis: list[str] = Field(default_factory=list)
    price_action_summary: list[str] = Field(default_factory=list)
    valuation_view: list[str] = Field(default_factory=list)
    important_news: list[StatementWithCitations] = Field(default_factory=list)
    bullish_factors: list[StatementWithCitations] = Field(default_factory=list)
    bearish_factors: list[StatementWithCitations] = Field(default_factory=list)
    recent_bullish_catalysts: list[StatementWithCitations] = Field(default_factory=list)
    recent_bearish_catalysts: list[StatementWithCitations] = Field(default_factory=list)
    key_news_items: list[StatementWithCitations] = Field(default_factory=list)
    base_case: list[str] = Field(default_factory=list)
    facts: list[StatementWithCitations] = Field(default_factory=list)
    bull_case: list[StatementWithCitations] = Field(default_factory=list)
    bear_case: list[StatementWithCitations] = Field(default_factory=list)
    decision_view: str = ""
    short_term_plan: TradePlan | None = None
    mid_term_plan: TradePlan | None = None
    long_term_thesis: list[str] = Field(default_factory=list)
    long_term_conditions: list[str] = Field(default_factory=list)
    thesis_breakers: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    key_monitoring_items: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    limitations: list[str] = Field(default_factory=list)
