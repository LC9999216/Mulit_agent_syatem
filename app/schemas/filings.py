from pydantic import BaseModel, Field

from app.schemas.common import StatementWithCitations


class FilingsOutput(BaseModel):
    business_summary: list[StatementWithCitations] = Field(default_factory=list)
    management_claims: list[StatementWithCitations] = Field(default_factory=list)
    risk_factor_summary: list[StatementWithCitations] = Field(default_factory=list)
    material_changes: list[StatementWithCitations] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
