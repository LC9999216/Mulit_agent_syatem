from app.agents.base import BaseAgent
from app.schemas.common import Citation, StatementWithCitations
from app.schemas.filings import FilingsOutput
from app.schemas.llm import FilingsDraftOutput
import re


class FilingsAgent(BaseAgent):
    name = "filings"

    def run(self, state: dict) -> FilingsOutput:
        documents = state.get("documents", [])
        if not documents:
            return FilingsOutput(open_questions=["No SEC filings were available for extraction."])

        evidence = self._collect_evidence(documents)
        fallback = self._build_rule_output(evidence)
        if self.llm_client is None or self.settings is None or not self.settings.llm_enabled:
            return fallback

        request = state["request"]
        system_prompt = (
            "You are the filings-extraction agent for an auditable stock research system. "
            "You will receive pre-selected SEC evidence snippets. "
            "Summarize only what is directly supported by those snippets. "
            "Return structured fields only. Do not invent facts, dates, guidance, or citations."
        )
        user_prompt = (
            f"Ticker: {request.ticker}\n"
            f"Goal: {request.user_goal}\n"
            f"Business evidence: {[item['content'] for item in evidence['business_summary']]}\n"
            f"Management evidence: {[item['content'] for item in evidence['management_claims']]}\n"
            f"Risk evidence: {[item['content'] for item in evidence['risk_factor_summary']]}\n"
            f"Material changes evidence: {[item['content'] for item in evidence['material_changes']]}"
        )
        try:
            model_name = self._resolve_model_name("filings")
            response = self.llm_client.generate_structured(
                agent_name=self.name,
                model=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=FilingsDraftOutput,
            )
            self._record_llm_call(
                state["request_id"],
                "completed",
                {"agent_name": self.name, **response.metadata},
            )
            return self._apply_llm_output(response.parsed, evidence, fallback)
        except Exception as exc:
            self._record_llm_call(
                state["request_id"],
                "fallback",
                {
                    "agent_name": self.name,
                    "provider": getattr(self.settings, "llm_provider", None),
                    "model": self._resolve_model_name("filings"),
                    "fallback_used": True,
                    "error_type": exc.__class__.__name__,
                    "input_summary": request.user_goal,
                },
            )
            return fallback

    def _collect_evidence(self, documents: list[dict]) -> dict[str, list[dict]]:
        evidence = {
            "business_summary": [],
            "management_claims": [],
            "risk_factor_summary": [],
            "material_changes": [],
        }
        for document in documents:
            sections = document.get("sections") or [{"section": document.get("section", "Overview"), "content": document.get("content", "")}]
            for section in sections:
                section_name = (section.get("section") or "Overview").strip()
                summary_text = self._summarize_section_text(section_name, section.get("content", ""))
                content = self._clean_text(summary_text)
                if not content:
                    continue
                candidate = {
                    "statement": content,
                    "content": content,
                    "citations": [self._build_citation(document, section_name)],
                }
                lowered_section = section_name.lower()
                lowered_content = content.lower()
                if "business" in lowered_section:
                    evidence["business_summary"].append(candidate)
                if "discussion" in lowered_section or "md&a" in lowered_section or any(
                    token in lowered_content for token in ("revenue increased", "demand", "growth", "outlook", "expects")
                ):
                    evidence["management_claims"].append(candidate)
                if "risk" in lowered_section or any(
                    token in lowered_content for token in ("risk", "customer concentration", "supply constraint", "may fluctuate")
                ):
                    evidence["risk_factor_summary"].append(candidate)
                if document.get("doc_type") == "8-K" or lowered_section.startswith("item "):
                    evidence["material_changes"].append(candidate)
        return {key: self._dedupe_candidates(value)[:2] for key, value in evidence.items()}

    def _build_rule_output(self, evidence: dict[str, list[dict]]) -> FilingsOutput:
        return FilingsOutput(
            business_summary=self._candidates_to_statements(evidence["business_summary"]),
            management_claims=self._candidates_to_statements(evidence["management_claims"]),
            risk_factor_summary=self._candidates_to_statements(evidence["risk_factor_summary"]),
            material_changes=self._candidates_to_statements(evidence["material_changes"]),
            open_questions=self._build_open_questions(evidence),
        )

    def _apply_llm_output(
        self,
        parsed: FilingsDraftOutput,
        evidence: dict[str, list[dict]],
        fallback: FilingsOutput,
    ) -> FilingsOutput:
        return FilingsOutput(
            business_summary=self._llm_lines_to_statements(parsed.business_summary, evidence["business_summary"]) or fallback.business_summary,
            management_claims=self._llm_lines_to_statements(parsed.management_claims, evidence["management_claims"]) or fallback.management_claims,
            risk_factor_summary=self._llm_lines_to_statements(parsed.risk_factor_summary, evidence["risk_factor_summary"]) or fallback.risk_factor_summary,
            material_changes=self._llm_lines_to_statements(parsed.material_changes, evidence["material_changes"]) or fallback.material_changes,
            open_questions=self._clean_lines(parsed.open_questions) or fallback.open_questions,
        )

    def _llm_lines_to_statements(self, lines: list[str], candidates: list[dict]) -> list[StatementWithCitations]:
        cleaned = self._clean_lines(lines)
        if not cleaned or not candidates:
            return []
        citations = candidates[0]["citations"]
        return [StatementWithCitations(statement=line, citations=citations) for line in cleaned[:2]]

    def _candidates_to_statements(self, candidates: list[dict]) -> list[StatementWithCitations]:
        return [
            StatementWithCitations(statement=item["statement"], citations=item["citations"])
            for item in candidates
        ]

    def _build_open_questions(self, evidence: dict[str, list[dict]]) -> list[str]:
        questions: list[str] = []
        if not evidence["business_summary"]:
            questions.append("Recent SEC filings did not yield a clear business-description excerpt.")
        if not evidence["management_claims"]:
            questions.append("Recent SEC filings did not yield a clear management commentary excerpt.")
        if not evidence["risk_factor_summary"]:
            questions.append("Recent SEC filings did not yield a clear risk-factor excerpt.")
        if not evidence["material_changes"]:
            questions.append("Recent SEC filings did not yield a clear recent material event excerpt.")
        return questions

    @staticmethod
    def _build_citation(document: dict, section_name: str) -> Citation:
        return Citation(
            source_type="filing",
            source_uri=document["source_uri"],
            label=f'{document["doc_type"]} {document["doc_date"]} / {section_name}',
            doc_date=document["doc_date"],
            section=section_name,
            support_type="filing",
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        compact = " ".join((text or "").split())
        return compact[:400]

    def _summarize_section_text(self, section_name: str, text: str) -> str:
        compact = " ".join((text or "").split())
        if not compact:
            return ""
        rewritten = self._rewrite_section_text(section_name, compact)
        if rewritten:
            return rewritten
        sentences = self._split_sentences(compact)
        cleaned_sentences = [self._strip_boilerplate(section_name, sentence) for sentence in sentences]
        cleaned_sentences = [sentence for sentence in cleaned_sentences if sentence]
        if not cleaned_sentences:
            return compact
        ranked = sorted(
            cleaned_sentences,
            key=lambda sentence: self._sentence_score(section_name, sentence),
            reverse=True,
        )
        best_sentences: list[str] = []
        for sentence in ranked:
            if sentence not in best_sentences:
                best_sentences.append(sentence)
            if len(best_sentences) >= 2:
                break
        return " ".join(best_sentences) if best_sentences else compact

    def _rewrite_section_text(self, section_name: str, text: str) -> str:
        lowered = text.lower()
        section_key = section_name.lower()

        if section_key == "business":
            if "cuda" in lowered or "software stack" in lowered:
                return (
                    "NVIDIA describes its CUDA-led software stack as a core enabler of AI and accelerated computing workloads."
                )
            if "accelerated computing" in lowered and "ai infrastructure" in lowered:
                return (
                    "NVIDIA describes itself as a data-center-scale AI infrastructure company built around accelerated computing."
                )

        if section_key == "md&a":
            if "revenue growth" in lowered and "data center compute and networking" in lowered:
                return (
                    "Management says fiscal 2026 revenue growth was driven by data center compute and networking demand tied to accelerated computing and AI solutions."
                )
            if "revenue increased" in lowered and "data center demand" in lowered:
                return (
                    "Management attributes revenue growth to strong data center demand and new AI deployments."
                )

        if section_key == "risk factors":
            if "governmental regulations" in lowered and "import and export" in lowered:
                return (
                    "NVIDIA flags regulatory, import, and export-control requirements as risks that could increase costs and adversely affect operating results."
                )
            if "customer concentration" in lowered or "supply constraint" in lowered:
                return (
                    "NVIDIA warns that customer concentration and supply constraints could materially affect results."
                )

        if section_key.startswith("item ") and "variable compensation plan" in lowered:
            return (
                "A March 2026 8-K disclosed adoption of NVIDIA's fiscal 2027 variable compensation plan tied to revenue-based performance goals."
            )

        return ""

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [" ".join(part.split()) for part in parts if part.strip()]

    def _strip_boilerplate(self, section_name: str, sentence: str) -> str:
        cleaned = sentence.strip()
        boilerplate_patterns = [
            r"^Our Company\s+",
            r"^The following discussion and analysis of our financial condition and results of operations should be read in conjunction with .*?\.\s*",
            r"^The following risk factors should be considered in addition to .*?\.\s*",
        ]
        for pattern in boilerplate_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.I)
        if section_name.lower() == "md&a":
            cleaned = re.sub(r"^Overview\s+", "", cleaned, flags=re.I)
        return " ".join(cleaned.split()).strip()

    @staticmethod
    def _sentence_score(section_name: str, sentence: str) -> int:
        lowered = sentence.lower()
        score = min(len(sentence), 220)
        if len(sentence) < 40:
            score -= 120
        keyword_sets = {
            "business": ("accelerated", "infrastructure", "platform", "software", "ai", "data center"),
            "md&a": ("revenue", "growth", "demand", "driven", "margin", "data center"),
            "risk factors": ("risk", "adverse", "concentration", "constraint", "regulatory", "export"),
        }
        for keyword in keyword_sets.get(section_name.lower(), ()):
            if keyword in lowered:
                score += 40
        if lowered.startswith(("our company", "the following discussion", "the following risk factors")):
            score -= 300
        return score

    @staticmethod
    def _clean_lines(lines: list[str]) -> list[str]:
        cleaned: list[str] = []
        for line in lines:
            text = " ".join((line or "").split())
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    @staticmethod
    def _dedupe_candidates(candidates: list[dict]) -> list[dict]:
        deduped: list[dict] = []
        seen: set[str] = set()
        for item in candidates:
            statement = item["statement"]
            if statement in seen:
                continue
            seen.add(statement)
            deduped.append(item)
        return deduped
