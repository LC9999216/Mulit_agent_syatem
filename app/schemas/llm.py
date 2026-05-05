from pydantic import BaseModel, Field

from app.schemas.common import ConfidenceLevel
from app.schemas.validation import ValidationIssue


class SupervisorPlanOutput(BaseModel):
    execution_plan: list[str] = Field(default_factory=list)
    required_agents: list[str] = Field(default_factory=list)
    blocking_conditions: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)


class ThesisDraftOutput(BaseModel):
    company_one_liner: str
    executive_summary: list[str] = Field(default_factory=list)
    base_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    decision_view: str = ""
    thesis_breakers: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    key_monitoring_items: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class FilingsDraftOutput(BaseModel):
    business_summary: list[str] = Field(default_factory=list)
    management_claims: list[str] = Field(default_factory=list)
    risk_factor_summary: list[str] = Field(default_factory=list)
    material_changes: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ValidationReviewOutput(BaseModel):
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
