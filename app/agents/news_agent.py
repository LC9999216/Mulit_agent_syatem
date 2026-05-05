from app.agents.base import BaseAgent
from app.schemas.common import Citation, ConfidenceLevel, StatementWithCitations
from app.schemas.news import NewsEvent, NewsOutput


class NewsAgent(BaseAgent):
    name = "news"

    def run(self, state: dict) -> NewsOutput:
        events = [NewsEvent.model_validate(item) for item in state.get("news_events", [])]
        events = sorted(events, key=lambda event: event.published_at or "", reverse=True)
        events = sorted(events, key=self._event_sort_key)

        important_news: list[StatementWithCitations] = []
        key_news_items: list[StatementWithCitations] = []
        bullish: list[StatementWithCitations] = []
        bearish: list[StatementWithCitations] = []
        opinion_news: list[StatementWithCitations] = []
        citations: list[Citation] = []

        for event in events[:8]:
            citation = Citation(
                source_type="news",
                source_uri=event.url,
                label=f"{event.source} / {event.title}",
                doc_date=event.published_at,
                section=event.topic_tag,
                support_type="news",
            )
            citations.append(citation)
            statement = StatementWithCitations(statement=self._summarize_event(event), citations=[citation])
            if self._should_include_in_key_news(event):
                important_news.append(statement)
                key_news_items.append(statement)
            elif event.source_quality == "opinion":
                opinion_news.append(statement)
            if event.source_class == "regulatory" or event.source_quality == "opinion":
                continue
            if event.sentiment_tag == "bullish":
                bullish.append(statement)
            elif event.sentiment_tag == "bearish":
                bearish.append(statement)

        filings_output = state.get("filings_output")
        financials_output = state.get("financials_output")
        market_output = state.get("market_output")

        if not important_news:
            important_news.extend(opinion_news[:2])
        if not important_news:
            important_news.extend(self._usable_statements(self._statement_group(filings_output, "material_changes"))[:1])
            important_news.extend(self._usable_statements(self._statement_group(market_output, "latest_price_analysis"))[:2])
        if not bullish:
            bullish.extend(self._usable_statements(self._statement_group(financials_output, "quality_checks"))[:2])
        if not bearish:
            bearish.extend(self._usable_statements(self._statement_group(filings_output, "risk_factor_summary"))[:1])
            if len(bearish) < 2:
                bearish.extend(self._usable_statements(self._statement_group(market_output, "valuation_view"))[: 2 - len(bearish)])

        important_news = self._dedupe_statements(important_news)[:5]
        bullish = self._dedupe_statements(bullish)[:3]
        bearish = self._dedupe_statements(bearish)[:3]

        return NewsOutput(
            important_news=important_news,
            bullish_factors=bullish,
            bearish_factors=bearish,
            bullish_catalysts=bullish,
            bearish_catalysts=bearish,
            key_news_items=key_news_items,
            raw_events=events,
            citations=citations,
            confidence=ConfidenceLevel.MEDIUM if (events or important_news or bullish or bearish) else ConfidenceLevel.LOW,
        )

    @staticmethod
    def _statement_group(output, attr_name: str) -> list[StatementWithCitations]:
        if output is None:
            return []
        if isinstance(output, dict):
            items = output.get(attr_name, []) or []
        else:
            items = getattr(output, attr_name, []) or []
        return [StatementWithCitations.model_validate(item) for item in items]

    @staticmethod
    def _dedupe_statements(items: list[StatementWithCitations]) -> list[StatementWithCitations]:
        deduped: list[StatementWithCitations] = []
        seen: set[str] = set()
        for item in items:
            key = item.statement.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @classmethod
    def _usable_statements(cls, items: list[StatementWithCitations]) -> list[StatementWithCitations]:
        return [item for item in items if cls._is_high_signal_statement(item.statement)]

    @staticmethod
    def _is_high_signal_statement(text: str) -> bool:
        normalized = (text or "").strip().lower()
        if not normalized:
            return False
        banned_markers = (
            "shall not be deemed",
            "section 18",
            "11 and 12(a)(2)",
            "incorporated by reference",
            "pursuant to the requirements",
        )
        if any(marker in normalized for marker in banned_markers):
            return False
        return len(normalized) <= 220

    @staticmethod
    def _summarize_event(event: NewsEvent) -> str:
        summary = " ".join((event.summary or "").split())
        if not summary:
            return event.title
        first_sentence = summary.split(". ")[0].strip()
        if len(first_sentence) <= 180:
            return first_sentence.rstrip(".") + "."
        trimmed = first_sentence[:177].rstrip()
        return f"{trimmed}..."

    @staticmethod
    def _event_sort_key(event: NewsEvent) -> tuple[int, int, int]:
        source_class_rank = 0 if event.source_class == "regulatory" else 1
        quality_rank_map = {
            "high": 0,
            "standard": 1,
            "opinion": 2,
        }
        topic_rank_map = {
            "earnings": 0,
            "regulation": 0,
            "partnership": 1,
            "product": 1,
            "general": 2,
            "filing": 0,
        }
        quality_rank = quality_rank_map.get(event.source_quality, 1)
        topic_rank = topic_rank_map.get(event.topic_tag, 2)
        return (source_class_rank, quality_rank, topic_rank)

    @staticmethod
    def _should_include_in_key_news(event: NewsEvent) -> bool:
        if event.source_class == "regulatory":
            return True
        return event.source_quality in {"high", "standard"}
