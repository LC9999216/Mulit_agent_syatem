from app.agents.base import BaseAgent
from app.schemas.common import ConfidenceLevel
from app.schemas.llm import ThesisDraftOutput
from app.schemas.report import FinalReport


class ThesisAgent(BaseAgent):
    name = "thesis"

    def run(self, state: dict) -> FinalReport:
        fallback = self._build_fallback(state)
        if self.llm_client is None or self.settings is None or not self.settings.llm_enabled:
            return fallback

        request = state["request"]
        filings = state["filings_output"]
        financials = state["financials_output"]
        market = state.get("market_output")
        news = state.get("news_output")
        facts = [*filings.business_summary, *financials.trend_findings]
        bull_case = [*financials.quality_checks]
        bear_evidence = [*filings.risk_factor_summary, *financials.anomalies]
        market_context = [*financials.market_context]
        system_prompt = (
            "You are the thesis-writing agent for an auditable stock research system. "
            "Produce only the requested structured fields. "
            "Stay within the supplied evidence and limitations. "
            "Do not invent citations or unsupported facts."
        )
        user_prompt = (
            f"Ticker: {request.ticker}\n"
            f"Goal: {request.user_goal}\n"
            f"Evidence facts: {[item.statement for item in facts]}\n"
            f"Bull case signals: {[item.statement for item in bull_case]}\n"
            f"Limitations: {state.get('limitations', [])}"
        )
        try:
            model_name = self._resolve_model_name("thesis")
            response = self.llm_client.generate_structured(
                agent_name=self.name,
                model=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=ThesisDraftOutput,
            )
            self._record_llm_call(
                state["request_id"],
                "completed",
                {"agent_name": self.name, **response.metadata},
            )
            parsed = response.parsed
            bear_case = self._build_bear_case(
                ticker=request.ticker,
                parsed_bear_case=parsed.bear_case,
                bear_evidence=bear_evidence,
                limitations=list(state.get("limitations", [])),
            )
            citations = []
            for item in [
                *self._statement_group(market, "price_action_summary"),
                *self._statement_group(market, "valuation_view"),
                *self._statement_group(market, "market_view"),
                *self._statement_group(news, "bullish_catalysts"),
                *self._statement_group(news, "bearish_catalysts"),
                *self._statement_group(news, "key_news_items"),
                *facts,
                *bull_case,
                *bear_case,
            ]:
                citations.extend(item.citations)
            base_case = self._build_base_case(
                ticker=request.ticker,
                parsed_base_case=parsed.base_case,
                facts=facts,
                bull_case=bull_case,
                bear_case=bear_case,
                market_context=market_context,
            )
            decision_view = self._build_decision_view(
                ticker=request.ticker,
                parsed_decision_view=parsed.decision_view,
                bull_case=bull_case,
                bear_case=bear_case,
                market_output=market,
                limitations=list(state.get("limitations", [])),
            )
            thesis_breakers = self._build_thesis_breakers(
                ticker=request.ticker,
                parsed_breakers=parsed.thesis_breakers,
                bear_case=bear_case,
                limitations=list(state.get("limitations", [])),
            )
            company_one_liner = self._build_company_one_liner(
                ticker=request.ticker,
                parsed_line=parsed.company_one_liner,
                facts=facts,
                bull_case=bull_case,
            )
            executive_summary = self._build_executive_summary(
                ticker=request.ticker,
                request_goal=request.user_goal,
                parsed_summary=parsed.executive_summary,
                facts=facts,
                bull_case=bull_case,
                market_context=market_context,
                market_output=market,
                limitations=list(state.get("limitations", [])),
            )
            uncertainties = self._build_uncertainties(
                ticker=request.ticker,
                parsed_uncertainties=parsed.uncertainties,
                limitations=list(state.get("limitations", [])),
                facts=facts,
            )
            monitoring_items = self._build_monitoring_items(
                ticker=request.ticker,
                parsed_items=parsed.key_monitoring_items,
                bull_case=bull_case,
                market_context=market_context,
            )
            what_happened = self._build_what_happened(
                ticker=request.ticker,
                facts=facts,
                filings_output=filings,
                news_output=news,
                market_output=market,
            )
            market_view = self._build_market_view(market_output=market)
            latest_price_analysis = self._build_latest_price_analysis(market_output=market)
            price_action_summary = self._build_price_action_summary(market_output=market)
            valuation_view = self._build_valuation_view(market_output=market)
            bullish_catalysts = self._build_catalysts(news_output=news, direction="bullish")
            bearish_catalysts = self._build_catalysts(news_output=news, direction="bearish")
            key_news_items = self._build_key_news_items(news_output=news)
            important_news = self._statement_group(news, "important_news")
            bullish_factors = self._statement_group(news, "bullish_factors") or bullish_catalysts
            bearish_factors = self._statement_group(news, "bearish_factors") or bearish_catalysts
            long_term_thesis = self._build_long_term_thesis(
                ticker=request.ticker,
                facts=facts,
                bull_case=bull_case,
                market_output=market,
            )
            long_term_conditions = self._build_long_term_conditions(
                ticker=request.ticker,
                bear_case=bear_case,
                limitations=list(state.get("limitations", [])),
            )
            return FinalReport(
                request_id=state["request_id"],
                ticker=request.ticker,
                company_one_liner=company_one_liner,
                executive_summary=executive_summary,
                what_happened=what_happened,
                market_view=market_view,
                latest_price_analysis=latest_price_analysis,
                price_action_summary=price_action_summary,
                valuation_view=valuation_view,
                important_news=important_news,
                bullish_factors=bullish_factors,
                bearish_factors=bearish_factors,
                recent_bullish_catalysts=bullish_catalysts,
                recent_bearish_catalysts=bearish_catalysts,
                key_news_items=key_news_items,
                base_case=base_case,
                facts=facts,
                bull_case=bull_case,
                bear_case=bear_case,
                decision_view=decision_view,
                short_term_plan=getattr(market, "short_term_plan", None),
                mid_term_plan=getattr(market, "mid_term_plan", None),
                long_term_thesis=long_term_thesis,
                long_term_conditions=long_term_conditions,
                thesis_breakers=thesis_breakers,
                uncertainties=uncertainties,
                key_monitoring_items=monitoring_items,
                citations=citations,
                confidence=parsed.confidence,
                limitations=list(state.get("limitations", [])),
            )
        except Exception as exc:
            self._record_llm_call(
                state["request_id"],
                "fallback",
                {
                    "agent_name": self.name,
                    "provider": getattr(self.settings, "llm_provider", None),
                    "model": self._resolve_model_name("thesis"),
                    "fallback_used": True,
                    "error_type": exc.__class__.__name__,
                    "input_summary": request.user_goal,
                },
            )
            return fallback

    def _build_fallback(self, state: dict) -> FinalReport:
        request = state["request"]
        filings = state["filings_output"]
        financials = state["financials_output"]
        market = state.get("market_output")
        news = state.get("news_output")
        state_limitations = list(state.get("limitations", []))
        facts = [*filings.business_summary, *financials.trend_findings]
        bull_case = [*financials.quality_checks]
        market_context = [*financials.market_context]
        bear_evidence = [*filings.risk_factor_summary, *financials.anomalies]
        bear_case = self._build_bear_case(
            ticker=request.ticker,
            parsed_bear_case=[],
            bear_evidence=bear_evidence,
            limitations=state_limitations,
        )
        citations = []
        for item in [
            *self._statement_group(market, "price_action_summary"),
            *self._statement_group(market, "valuation_view"),
            *self._statement_group(market, "market_view"),
            *self._statement_group(news, "bullish_catalysts"),
            *self._statement_group(news, "bearish_catalysts"),
            *self._statement_group(news, "key_news_items"),
            *facts,
            *bull_case,
            *bear_case,
        ]:
            citations.extend(item.citations)
        return FinalReport(
            request_id=state["request_id"],
            ticker=request.ticker,
            company_one_liner=self._build_company_one_liner(
                ticker=request.ticker,
                parsed_line="",
                facts=facts,
                bull_case=bull_case,
            ),
            executive_summary=self._build_executive_summary(
                ticker=request.ticker,
                request_goal=request.user_goal,
                parsed_summary=[],
                facts=facts,
                bull_case=bull_case,
                market_context=market_context,
                market_output=market,
                limitations=state_limitations,
            ),
            what_happened=self._build_what_happened(
                ticker=request.ticker,
                facts=facts,
                filings_output=filings,
                news_output=news,
                market_output=market,
            ),
            market_view=self._build_market_view(market_output=market),
            latest_price_analysis=self._build_latest_price_analysis(market_output=market),
            price_action_summary=self._build_price_action_summary(market_output=market),
            valuation_view=self._build_valuation_view(market_output=market),
            important_news=self._statement_group(news, "important_news"),
            bullish_factors=self._statement_group(news, "bullish_factors") or self._build_catalysts(news_output=news, direction="bullish"),
            bearish_factors=self._statement_group(news, "bearish_factors") or self._build_catalysts(news_output=news, direction="bearish"),
            recent_bullish_catalysts=self._build_catalysts(news_output=news, direction="bullish"),
            recent_bearish_catalysts=self._build_catalysts(news_output=news, direction="bearish"),
            key_news_items=self._build_key_news_items(news_output=news),
            base_case=self._build_base_case(
                ticker=request.ticker,
                parsed_base_case=[],
                facts=facts,
                bull_case=bull_case,
                bear_case=bear_case,
                market_context=market_context,
            ),
            facts=facts,
            bull_case=bull_case,
            bear_case=bear_case,
            decision_view=self._build_decision_view(
                ticker=request.ticker,
                parsed_decision_view="",
                bull_case=bull_case,
                bear_case=bear_case,
                market_output=market,
                limitations=state_limitations,
            ),
            short_term_plan=getattr(market, "short_term_plan", None),
            mid_term_plan=getattr(market, "mid_term_plan", None),
            long_term_thesis=self._build_long_term_thesis(
                ticker=request.ticker,
                facts=facts,
                bull_case=bull_case,
                market_output=market,
            ),
            long_term_conditions=self._build_long_term_conditions(
                ticker=request.ticker,
                bear_case=bear_case,
                limitations=state_limitations,
            ),
            thesis_breakers=self._build_thesis_breakers(
                ticker=request.ticker,
                parsed_breakers=[],
                bear_case=bear_case,
                limitations=state_limitations,
            ),
            uncertainties=self._build_uncertainties(
                ticker=request.ticker,
                parsed_uncertainties=[],
                limitations=state_limitations,
                facts=facts,
            ),
            key_monitoring_items=self._build_monitoring_items(
                ticker=request.ticker,
                parsed_items=[],
                bull_case=bull_case,
                market_context=market_context,
            ),
            citations=citations,
            confidence=ConfidenceLevel.MEDIUM,
            limitations=state_limitations or ([] if facts else ["Report was generated with limited evidence."]),
        )

    @staticmethod
    def _statement_group(output, attr_name: str) -> list:
        if output is None:
            return []
        return list(getattr(output, attr_name, []) or [])

    @staticmethod
    def _clean_lines(items: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in items:
            text = (item or "").strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def _build_company_one_liner(self, *, ticker: str, parsed_line: str, facts: list, bull_case: list) -> str:
        line = (parsed_line or "").strip()
        if line:
            return line
        if facts and bull_case:
            return (
                f"{ticker} remains a high-momentum name where disclosed demand commentary is currently "
                f"supported by strong reported profitability and cash generation."
            )
        if facts:
            return f"{ticker} currently merits follow-up based on filings-backed operating momentum, but the evidence set remains incomplete."
        return f"{ticker} does not yet have enough verified evidence in the system for a strong research conclusion."

    def _build_what_happened(self, *, ticker: str, facts: list, filings_output, news_output, market_output) -> list[str]:
        lines: list[str] = []
        for item in self._statement_group(filings_output, "material_changes")[:2]:
            lines.append(item.statement)
        for item in self._build_key_news_items(news_output=news_output)[:2]:
            lines.append(item.statement)
        for item in self._statement_group(market_output, "price_action_summary")[:1]:
            lines.append(item.statement)
        if facts:
            lines.append(facts[0].statement)
        if not lines:
            lines.append(f"No major verified operating or news developments were captured for {ticker}.")
        return self._clean_lines(lines)[:3]

    def _build_market_view(self, *, market_output) -> list[str]:
        lines = [item.statement for item in self._statement_group(market_output, "market_view")]
        return self._clean_lines(lines)[:3]

    def _build_latest_price_analysis(self, *, market_output) -> list[str]:
        lines = [item.statement for item in self._statement_group(market_output, "latest_price_analysis")]
        if not lines:
            lines.extend(self._build_market_view(market_output=market_output))
            lines.extend(self._build_price_action_summary(market_output=market_output)[:1])
        return self._clean_lines(lines)[:4]

    def _build_price_action_summary(self, *, market_output) -> list[str]:
        lines = [item.statement for item in self._statement_group(market_output, "price_action_summary")]
        return self._clean_lines(lines)[:3]

    def _build_valuation_view(self, *, market_output) -> list[str]:
        lines = [item.statement for item in self._statement_group(market_output, "valuation_view")]
        return self._clean_lines(lines)[:3]

    def _build_catalysts(self, *, news_output, direction: str) -> list:
        attr_name = "bullish_catalysts" if direction == "bullish" else "bearish_catalysts"
        return self._statement_group(news_output, attr_name)[:3]

    def _build_key_news_items(self, *, news_output) -> list:
        items = self._statement_group(news_output, "key_news_items")
        raw_events = list(getattr(news_output, "raw_events", []) or []) if news_output is not None else []
        if not items or not raw_events:
            return items[:5]

        filtered = []
        for event, item in zip(raw_events, items):
            source_class = getattr(event, "source_class", None)
            source_quality = getattr(event, "source_quality", "standard")
            if source_class == "regulatory" or source_quality in {"high", "standard"}:
                filtered.append(item)
        return filtered[:5] if filtered else items[:5]

    def _build_executive_summary(
        self,
        *,
        ticker: str,
        request_goal: str,
        parsed_summary: list[str],
        facts: list,
        bull_case: list,
        market_context: list,
        market_output,
        limitations: list[str],
    ) -> list[str]:
        summary = [
            item for item in self._clean_lines(parsed_summary) if not self._is_generic_executive_summary_line(item)
        ]
        fact_lines = [item.statement for item in facts if item.statement]
        bull_lines = [item.statement for item in bull_case if item.statement]
        market_lines = [
            item.statement
            for item in [
                *self._statement_group(market_output, "market_view"),
                *self._statement_group(market_output, "valuation_view"),
                *self._statement_group(market_output, "price_action_summary"),
                *market_context,
            ]
            if getattr(item, "statement", "")
        ]
        if not summary and fact_lines:
            if market_lines:
                summary.append(
                    f"{ticker} still has strong operating support in the current evidence set: {fact_lines[0]} "
                    f"At the same time, {self._lowercase_first(market_lines[0])}"
                )
            else:
                summary.append(fact_lines[0])
        prioritized_lines = [*fact_lines[:2], *bull_lines[:2]]
        for line in prioritized_lines:
            if len(summary) >= 4:
                break
            summary.append(line)
        for line in market_lines:
            if len(summary) >= 4:
                break
            summary.append(line)
        if len(summary) < 3 and limitations:
            summary.append(
                f"The current view on {ticker} should remain evidence-bound until the open data gaps are closed."
            )
        if len(summary) < 3:
            summary.append(
                f"{ticker} remains worth monitoring, but the setup should be treated as judgment-intensive rather than a simple follow-the-trend call."
            )
        return self._clean_lines(summary)[:4]

    def _build_base_case(
        self,
        *,
        ticker: str,
        parsed_base_case: list[str],
        facts: list,
        bull_case: list,
        bear_case: list,
        market_context: list,
    ) -> list[str]:
        base_case = self._clean_lines(parsed_base_case)
        if not base_case and facts:
            base_case.append(f"{ticker}'s base case assumes current operating momentum remains positive but moderates from unusually strong recent growth.")
        if len(base_case) < 2 and bull_case:
            base_case.append("The current thesis depends on strong profitability and cash generation continuing as demand normalizes.")
        if len(base_case) < 3 and bear_case:
            base_case.append("The base case still requires close monitoring of the main downside risks highlighted in filings and validation checks.")
        if len(base_case) < 3 and market_context:
            base_case.append("Market performance has been strong, so execution matters more than simple headline growth from here.")
        return self._clean_lines(base_case)[:3]

    def _build_bear_case(
        self,
        *,
        ticker: str,
        parsed_bear_case: list[str],
        bear_evidence: list,
        limitations: list[str],
    ) -> list:
        lines = self._clean_lines(parsed_bear_case)
        statements = []
        if lines and bear_evidence:
            citations = bear_evidence[0].citations
            for line in lines[:2]:
                statements.append(type(bear_evidence[0]).model_validate({"statement": line, "citations": citations}))
            return statements
        if bear_evidence:
            for item in bear_evidence[:2]:
                statements.append(item)
        elif limitations:
            from app.schemas.common import StatementWithCitations

            for limitation in limitations[:2]:
                statements.append(StatementWithCitations(statement=limitation, citations=[]))
        if not statements:
            from app.schemas.common import StatementWithCitations

            statements.append(
                StatementWithCitations(
                    statement=f"The bear case for {ticker} is that current demand strength and margin durability may prove less sustainable than recent results imply.",
                    citations=[],
                )
            )
        return statements[:2]

    def _build_decision_view(
        self,
        *,
        ticker: str,
        parsed_decision_view: str,
        bull_case: list,
        bear_case: list,
        market_output,
        limitations: list[str],
    ) -> str:
        decision_view = (parsed_decision_view or "").strip()
        if decision_view and not self._is_generic_decision_view(decision_view):
            return decision_view
        market_lines = [
            item.statement
            for item in [
                *self._statement_group(market_output, "valuation_view"),
                *self._statement_group(market_output, "market_view"),
            ]
            if getattr(item, "statement", "")
        ]
        if bull_case and bear_case:
            if market_lines:
                return (
                    f"Continue tracking {ticker}, but keep the stance execution-sensitive: "
                    f"{bull_case[0].statement.rstrip('.')} However, {self._lowercase_first(market_lines[0])}"
                )
            return f"Continue tracking {ticker}, but treat the name as execution-sensitive because strong quality indicators coexist with clear downside conditions."
        if bull_case:
            if market_lines:
                return (
                    f"Continue tracking {ticker}, but keep the stance execution-sensitive: "
                    f"{bull_case[0].statement.rstrip('.')} However, {self._lowercase_first(market_lines[0])}"
                )
            return f"Continue tracking {ticker} primarily for fundamental strength, while waiting for a cleaner downside/risk read."
        if limitations:
            return f"Do not rely on a strong directional decision for {ticker} until the current evidence gaps are closed."
        return f"Maintain a watchlist stance on {ticker} until the thesis is supported by a fuller evidence set."

    def _build_thesis_breakers(
        self,
        *,
        ticker: str,
        parsed_breakers: list[str],
        bear_case: list,
        limitations: list[str],
    ) -> list[str]:
        breakers = self._clean_lines(parsed_breakers)
        if not breakers and bear_case:
            for item in bear_case[:3]:
                statement = (item.statement or "").strip()
                if not statement:
                    continue
                breakers.append(self._rewrite_bear_statement_as_breaker(ticker=ticker, statement=statement))
        if len(breakers) < 2:
            breakers.append(f"A material slowdown in demand or profitability would weaken the {ticker} thesis.")
        if len(breakers) < 3 and limitations:
            for limitation in limitations:
                breakers.append(self._rewrite_limitation_as_breaker(ticker=ticker, limitation=limitation))
                if len(self._clean_lines(breakers)) >= 3:
                    break
        return self._clean_lines(breakers)[:3]

    def _rewrite_bear_statement_as_breaker(self, *, ticker: str, statement: str) -> str:
        lower = statement.lower()

        if "export control" in lower or "regulator" in lower or "restriction" in lower or "geopolitical" in lower:
            return (
                f"If export control, regulatory, or geopolitical restrictions tighten further, the {ticker} thesis weakens "
                "because shipment capacity, customer access, or product mix could deteriorate."
            )
        if "customer concentration" in lower or "concentration" in lower or "hyperscale" in lower or "customer" in lower:
            return (
                f"If hyperscale demand slows or customer concentration worsens, the {ticker} thesis weakens because current growth "
                "would prove less durable than the market is assuming."
            )
        if "margin" in lower or "profit" in lower or "cash flow" in lower or "profitability" in lower:
            return (
                f"If gross margin, operating leverage, or cash generation materially deteriorates, the {ticker} thesis weakens "
                "because the current quality profile would no longer support a premium view."
            )
        if "inventory" in lower or "pricing" in lower or "competition" in lower:
            return (
                f"If pricing pressure, competition, or inventory imbalances intensify, the {ticker} thesis weakens because current "
                "earnings power would likely be overstated."
            )

        normalized = statement.rstrip(".")
        return f"If {normalized[:1].lower()}{normalized[1:]}, the {ticker} thesis weakens."

    def _rewrite_limitation_as_breaker(self, *, ticker: str, limitation: str) -> str:
        lower = limitation.lower().rstrip(".")
        if lower.startswith("missing ") or lower.startswith("no ") or lower.startswith("limited "):
            return f"If upcoming disclosures fail to close this evidence gap, the {ticker} thesis should remain low-conviction: {lower}."
        return f"If this limitation remains unresolved in future updates, the {ticker} thesis should be downgraded: {lower}."

    def _build_uncertainties(self, *, ticker: str, parsed_uncertainties: list[str], limitations: list[str], facts: list) -> list[str]:
        uncertainties = self._clean_lines(parsed_uncertainties)
        if not uncertainties and limitations:
            uncertainties.extend(limitations[:2])
        if not uncertainties and facts:
            uncertainties.append(f"Sustained demand strength for {ticker} still needs confirmation across upcoming reporting periods.")
        if not uncertainties:
            uncertainties.append(f"The current evidence set for {ticker} is too narrow to underwrite a high-conviction view.")
        return self._clean_lines(uncertainties)[:3]

    def _build_monitoring_items(
        self,
        *,
        ticker: str,
        parsed_items: list[str],
        bull_case: list,
        market_context: list,
    ) -> list[str]:
        monitoring_items = self._clean_lines(parsed_items)
        if not monitoring_items and bull_case:
            monitoring_items.append("Gross margin trajectory")
            monitoring_items.append("Free cash flow margin")
        if not monitoring_items and market_context:
            monitoring_items.append("Trailing 12-month stock performance versus operating results")
        if not monitoring_items:
            monitoring_items.extend(
                [
                    f"{ticker} next quarterly revenue growth",
                    "Management commentary on demand durability",
                ]
            )
        return self._clean_lines(monitoring_items)[:4]

    def _build_long_term_thesis(self, *, ticker: str, facts: list, bull_case: list, market_output) -> list[str]:
        lines: list[str] = []
        if facts:
            lines.append(facts[0].statement)
        if bull_case:
            lines.append(bull_case[0].statement)
        valuation = self._build_valuation_view(market_output=market_output)
        if valuation:
            lines.append(f"Long-term upside still depends on justifying today's premium valuation: {valuation[0]}")
        if not lines:
            lines.append(f"{ticker} needs stronger evidence before a durable long-term thesis can be underwritten.")
        return self._clean_lines(lines)[:3]

    def _build_long_term_conditions(self, *, ticker: str, bear_case: list, limitations: list[str]) -> list[str]:
        lines = [
            f"{ticker} data center and AI demand must remain structurally strong.",
            "Gross margin and cash generation must stay elevated enough to support a premium multiple.",
            "Regulatory or export restrictions must not materially worsen.",
        ]
        for item in bear_case[:1]:
            lines.append(item.statement)
        for limitation in limitations[:1]:
            lines.append(limitation)
        return self._clean_lines(lines)[:4]

    @staticmethod
    def _is_generic_executive_summary_line(text: str) -> bool:
        normalized = text.strip().lower()
        generic_markers = (
            "screens well for the stated goal",
            "based on the provided evidence",
            "appears well positioned",
            "stated goal",
        )
        return any(marker in normalized for marker in generic_markers)

    @staticmethod
    def _is_generic_decision_view(text: str) -> bool:
        normalized = text.strip().lower().rstrip(".")
        if normalized.startswith("continue tracking ") and len(normalized.split()) <= 4:
            return True
        return normalized in {"continue tracking", "continue tracking nvda"}

    @staticmethod
    def _lowercase_first(text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return cleaned
        return cleaned[:1].lower() + cleaned[1:]
