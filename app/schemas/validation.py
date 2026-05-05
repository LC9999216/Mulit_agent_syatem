from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    path: str
    message: str
    severity: str = "error"


class ValidationResult(BaseModel):
    passed: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
