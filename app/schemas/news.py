from pydantic import BaseModel, Field

from app.schemas.common import Citation, ConfidenceLevel, StatementWithCitations


class NewsEvent(BaseModel):
    title: str
    summary: str
    source: str
    url: str
    published_at: str | None = None
    sentiment_tag: str = "neutral"
    topic_tag: str = "general"
    source_class: str = "market_news"
    source_quality: str = "standard"


class NewsOutput(BaseModel):
    important_news: list[StatementWithCitations] = Field(default_factory=list)
    bullish_factors: list[StatementWithCitations] = Field(default_factory=list)
    bearish_factors: list[StatementWithCitations] = Field(default_factory=list)
    bullish_catalysts: list[StatementWithCitations] = Field(default_factory=list)
    bearish_catalysts: list[StatementWithCitations] = Field(default_factory=list)
    key_news_items: list[StatementWithCitations] = Field(default_factory=list)
    raw_events: list[NewsEvent] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
