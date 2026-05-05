from pydantic import BaseModel, Field

from app.schemas.common import Citation, ConfidenceLevel, StatementWithCitations


class MetricPoint(BaseModel):
    period: str
    value: float
    source: str


class FinancialsOutput(BaseModel):
    key_metrics_table: dict[str, list[MetricPoint]] = Field(default_factory=dict)
    trend_findings: list[StatementWithCitations] = Field(default_factory=list)
    quality_checks: list[StatementWithCitations] = Field(default_factory=list)
    anomalies: list[StatementWithCitations] = Field(default_factory=list)
    market_context: list[StatementWithCitations] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
