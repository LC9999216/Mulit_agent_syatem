from app.agents.base import BaseAgent
from app.schemas.llm import ValidationReviewOutput
from app.schemas.report import FinalReport
from app.schemas.validation import ValidationIssue, ValidationResult


class ValidationAgent(BaseAgent):
    name = "validation"

    def run(self, state: dict) -> ValidationResult:
        fallback = self._run_rules(state)
        if self.llm_client is None or self.settings is None or not self.settings.llm_enabled:
            return fallback

        report = FinalReport.model_validate(state["draft_report"])
        system_prompt = (
            "You are the validation agent for an auditable stock research system. "
            "Return only structured validation findings. "
            "Focus on unsupported inference, missing limitations, and evidence-bound wording."
        )
        user_prompt = (
            f"Ticker: {report.ticker}\n"
            f"Executive summary: {report.executive_summary}\n"
            f"Facts: {[item.statement for item in report.facts]}\n"
            f"Bull case: {[item.statement for item in report.bull_case]}\n"
            f"Bear case: {[item.statement for item in report.bear_case]}\n"
            f"Limitations: {report.limitations}\n"
            f"Citation count: {len(report.citations)}"
        )
        try:
            model_name = self._resolve_model_name("validation")
            response = self.llm_client.generate_structured(
                agent_name=self.name,
                model=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=ValidationReviewOutput,
            )
            self._record_llm_call(
                state["request_id"],
                "completed",
                {"agent_name": self.name, **response.metadata},
            )
            errors = [*fallback.errors, *response.parsed.errors]
            warnings = [*fallback.warnings, *response.parsed.warnings]
            return ValidationResult(passed=not errors, errors=errors, warnings=warnings)
        except Exception as exc:
            self._record_llm_call(
                state["request_id"],
                "fallback",
                {
                    "agent_name": self.name,
                    "provider": getattr(self.settings, "llm_provider", None),
                    "model": self._resolve_model_name("validation"),
                    "fallback_used": True,
                    "error_type": exc.__class__.__name__,
                    "input_summary": report.ticker,
                },
            )
            return fallback

    def _run_rules(self, state: dict) -> ValidationResult:
        report = FinalReport.model_validate(state["draft_report"])
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        for section_name in ("facts", "bull_case", "bear_case"):
            items = getattr(report, section_name)
            for index, item in enumerate(items):
                if not item.citations:
                    errors.append(
                        ValidationIssue(
                            path=f"{section_name}[{index}]",
                            message="Statement is missing citations.",
                        )
                    )

        if not report.citations:
            warnings.append(
                ValidationIssue(
                    path="citations",
                    message="Flattened citation list is empty.",
                    severity="warning",
                )
            )

        if not report.base_case:
            errors.append(
                ValidationIssue(path="base_case", message="Base case must not be empty.")
            )
        if not report.bear_case:
            errors.append(
                ValidationIssue(path="bear_case", message="Bear case must not be empty.")
            )
        if not report.decision_view.strip():
            errors.append(
                ValidationIssue(path="decision_view", message="Decision view must not be empty.")
            )
        if not report.thesis_breakers:
            errors.append(
                ValidationIssue(path="thesis_breakers", message="Thesis breakers must not be empty.")
            )

        return ValidationResult(passed=not errors, errors=errors, warnings=warnings)
