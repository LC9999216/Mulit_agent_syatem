from enum import StrEnum

from pydantic import BaseModel, Field


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Citation(BaseModel):
    source_type: str
    source_uri: str
    label: str
    doc_date: str | None = None
    section: str | None = None
    support_type: str | None = None


class StatementWithCitations(BaseModel):
    statement: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)


class InsufficientData(BaseModel):
    reason: str
    missing_fields: list[str] = Field(default_factory=list)
