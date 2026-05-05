from pydantic import BaseModel, Field, field_validator


class CompanyAnalysisRequest(BaseModel):
    ticker: str
    user_goal: str = Field(min_length=1)
    time_scope: str = "latest"
    include_market: bool = True
    include_risk: bool = False

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("ticker cannot be blank")
        return cleaned

    @field_validator("user_goal")
    @classmethod
    def validate_user_goal(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("user_goal cannot be blank")
        return cleaned
