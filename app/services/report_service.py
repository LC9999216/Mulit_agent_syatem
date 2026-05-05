from pathlib import Path

from app.schemas.common import Citation, StatementWithCitations
from app.schemas.report import FinalReport


class ReportService:
    def flatten_citations(self, report: FinalReport) -> FinalReport:
        unique: dict[tuple[str, str, str], Citation] = {}
        for citation in report.citations:
            unique[(citation.source_type, citation.source_uri, citation.label)] = citation
        for group in (
            report.important_news,
            report.bullish_factors,
            report.bearish_factors,
            report.recent_bullish_catalysts,
            report.recent_bearish_catalysts,
            report.key_news_items,
            report.facts,
            report.bull_case,
            report.bear_case,
        ):
            for statement in group:
                for citation in statement.citations:
                    unique[(citation.source_type, citation.source_uri, citation.label)] = citation
        return report.model_copy(update={"citations": list(unique.values())})

    def render_markdown(self, report: FinalReport) -> str:
        lines = [
            f"# {report.ticker} Research Report",
            "",
            f"Request ID: `{report.request_id}`",
            "",
            f"One-liner: {report.company_one_liner}",
            "",
            f"Confidence: `{report.confidence}`",
            "",
        ]
        lines.extend(self._render_bullet_section("Executive Summary", report.executive_summary))
        lines.extend(self._render_bullet_section("Latest Price Analysis", report.latest_price_analysis))
        lines.extend(self._render_statement_section("Important News", report.important_news))
        lines.extend(self._render_statement_section("Bullish Factors", report.bullish_factors))
        lines.extend(self._render_statement_section("Bearish Factors", report.bearish_factors))
        lines.extend(self._render_trade_plan_section("Short-Term Plan", report.short_term_plan))
        lines.extend(self._render_trade_plan_section("Mid-Term Plan", report.mid_term_plan))
        lines.extend(self._render_bullet_section("Long-Term Thesis", report.long_term_thesis))
        lines.extend(self._render_bullet_section("Long-Term Conditions", report.long_term_conditions))
        lines.extend(self._render_bullet_section("Base Case", report.base_case))
        lines.extend(self._render_statement_section("Facts", report.facts))
        lines.extend(self._render_statement_section("Bull Case", report.bull_case))
        lines.extend(self._render_statement_section("Bear Case", report.bear_case))
        lines.extend(self._render_single_value_section("Decision View", report.decision_view))
        lines.extend(self._render_bullet_section("Thesis Breakers", report.thesis_breakers))
        lines.extend(self._render_bullet_section("Uncertainties", report.uncertainties))
        lines.extend(self._render_bullet_section("Key Monitoring Items", report.key_monitoring_items))
        lines.extend(self._render_bullet_section("Limitations", report.limitations))
        lines.extend(self._render_citations(report.citations))
        return "\n".join(lines).strip() + "\n"

    def export_markdown(self, report: FinalReport, output_dir: Path | str) -> Path:
        base_dir = Path(output_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        output_path = base_dir / f"{report.request_id}.md"
        output_path.write_text(self.render_markdown(report), encoding="utf-8")
        return output_path

    @staticmethod
    def _render_bullet_section(title: str, items: list[str]) -> list[str]:
        lines = [f"## {title}", ""]
        if not items:
            lines.append("- None")
        else:
            lines.extend(f"- {item}" for item in items)
        lines.append("")
        return lines

    def _render_statement_section(self, title: str, items: list[StatementWithCitations]) -> list[str]:
        lines = [f"## {title}", ""]
        if not items:
            lines.append("- None")
            lines.append("")
            return lines
        for item in items:
            lines.append(f"- {item.statement}")
            for citation in item.citations:
                lines.append(f"  Source: {citation.label} <{citation.source_uri}>")
        lines.append("")
        return lines

    @staticmethod
    def _render_single_value_section(title: str, value: str) -> list[str]:
        lines = [f"## {title}", ""]
        lines.append(f"- {value}" if value else "- None")
        lines.append("")
        return lines

    @staticmethod
    def _render_trade_plan_section(title: str, plan) -> list[str]:
        lines = [f"## {title}", ""]
        if plan is None:
            lines.append("- None")
            lines.append("")
            return lines
        lines.append(f"- Bias: {plan.bias}")
        lines.append(f"- Entry Context: {plan.entry_context or 'None'}")
        lines.append(f"- Target Price: {plan.target_price if plan.target_price is not None else 'None'}")
        lines.append(f"- Stop Loss: {plan.stop_loss if plan.stop_loss is not None else 'None'}")
        lines.append(f"- Position Size: {plan.position_size_pct if plan.position_size_pct is not None else 'None'}")
        for item in plan.rationale:
            lines.append(f"- Rationale: {item}")
        for item in plan.invalidators:
            lines.append(f"- Invalidator: {item}")
        lines.append("")
        return lines

    @staticmethod
    def _render_citations(citations: list[Citation]) -> list[str]:
        lines = ["## Citations", ""]
        if not citations:
            lines.append("- None")
            lines.append("")
            return lines
        for citation in citations:
            lines.append(f"- {citation.label}: <{citation.source_uri}>")
        lines.append("")
        return lines
