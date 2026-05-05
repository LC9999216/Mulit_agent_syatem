from app.agents.base import BaseAgent
from app.schemas.llm import SupervisorPlanOutput


class SupervisorAgent(BaseAgent):
    name = "supervisor"

    def run(self, state: dict) -> dict:
        fallback = self._build_fallback(state)
        if self.llm_client is None or self.settings is None or not self.settings.llm_enabled:
            return fallback

        request = state["request"]
        system_prompt = (
            "You are the supervisor agent for an auditable stock research workflow. "
            "Return only a structured plan, grounded in the available request and limitations. "
            "Do not invent unavailable data sources."
        )
        user_prompt = (
            f"Ticker: {request.ticker}\n"
            f"Goal: {request.user_goal}\n"
            f"Include market context: {request.include_market}\n"
            f"Existing limitations: {state.get('limitations', [])}"
        )
        try:
            model_name = self._resolve_model_name("supervisor")
            response = self.llm_client.generate_structured(
                agent_name=self.name,
                model=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=SupervisorPlanOutput,
            )
            self._record_llm_call(
                state["request_id"],
                "completed",
                {"agent_name": self.name, **response.metadata},
            )
            return response.parsed.model_dump(mode="json")
        except Exception as exc:
            self._record_llm_call(
                state["request_id"],
                "fallback",
                {
                    "agent_name": self.name,
                    "provider": getattr(self.settings, "llm_provider", None),
                    "model": self._resolve_model_name("supervisor"),
                    "fallback_used": True,
                    "error_type": exc.__class__.__name__,
                    "input_summary": request.user_goal,
                },
            )
            return fallback

    def _build_fallback(self, state: dict) -> dict:
        request = state["request"]
        required_agents = ["filings", "financials", "thesis", "validation"]
        execution_plan = [
            "init",
            "fetch_data",
            "run_filings_agent",
            "run_financials_agent",
            "run_thesis_agent",
            "run_validation_agent",
            "finalize",
        ]
        if request.include_market:
            execution_plan.insert(4, "include_market_context")
        return {
            "execution_plan": execution_plan,
            "required_agents": required_agents,
            "blocking_conditions": [],
            "focus_areas": [],
        }
