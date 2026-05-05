from pydantic import BaseModel, Field

from app.schemas.common import Citation, ConfidenceLevel, StatementWithCitations
from app.schemas.financials import MetricPoint


class TradePlan(BaseModel):
    horizon: str
    bias: str
    entry_context: str = ""
    target_price: float | None = None
    stop_loss: float | None = None
    position_size_pct: float | None = None
    rationale: list[str] = Field(default_factory=list)
    invalidators: list[str] = Field(default_factory=list)


class MarketOutput(BaseModel):
    key_metrics_table: dict[str, list[MetricPoint]] = Field(default_factory=dict)
    latest_price_analysis: list[StatementWithCitations] = Field(default_factory=list)
    price_action_summary: list[StatementWithCitations] = Field(default_factory=list)
    valuation_view: list[StatementWithCitations] = Field(default_factory=list)
    market_view: list[StatementWithCitations] = Field(default_factory=list)
    short_term_plan: TradePlan | None = None
    mid_term_plan: TradePlan | None = None
    citations: list[Citation] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
