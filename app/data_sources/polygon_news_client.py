from __future__ import annotations

from datetime import date, timedelta
import re

import httpx


class PolygonNewsClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=20.0)

    def fetch_company_news(self, ticker: str, company_aliases: set[str] | None = None) -> list[dict]:
        if not self.api_key:
            return []

        end = date.today()
        start = end - timedelta(days=14)
        response = self.http_client.get(
            f"{self.base_url}/v2/reference/news",
            params={
                "ticker": ticker,
                "published_utc.gte": start.isoformat(),
                "published_utc.lte": end.isoformat(),
                "sort": "published_utc",
                "order": "desc",
                "limit": 10,
                "apiKey": self.api_key,
            },
        )
        response.raise_for_status()
        payload = response.json() or {}
        aliases = {ticker.upper()}
        if company_aliases:
            aliases.update(alias.upper() for alias in company_aliases if alias)

        events: list[dict] = []
        for item in payload.get("results", []) or []:
            tickers = [str(symbol).upper() for symbol in item.get("tickers") or []]
            if ticker.upper() not in tickers:
                continue
            title = item.get("title") or ""
            summary = item.get("description") or title
            if not self._is_company_primary_in_title(title, aliases):
                continue
            publisher = item.get("publisher") or {}
            source_name = publisher.get("name") or "Polygon News"
            events.append(
                {
                    "title": title,
                    "summary": summary,
                    "source": source_name,
                    "url": item.get("article_url") or "",
                    "published_at": item.get("published_utc"),
                    "sentiment_tag": self._infer_sentiment(f"{title} {summary}"),
                    "topic_tag": self._infer_topic(f"{title} {summary}"),
                    "source_class": "market_news",
                    "source_quality": self._infer_source_quality(title=title, source_name=source_name),
                }
            )
        return [event for event in events if event["url"]][:6]

    @classmethod
    def _is_company_primary_in_title(cls, title: str, aliases: set[str]) -> bool:
        normalized_title = cls._normalize_text(title)
        if cls._is_comparison_or_competitor_led_title(normalized_title):
            return False
        for alias in aliases:
            token = cls._normalize_text(alias)
            if not token:
                continue
            if normalized_title == token:
                return True
            if normalized_title.startswith(f"{token} "):
                return True
            if f" {token} " in f" {normalized_title} ":
                return True
        return False

    @staticmethod
    def _is_comparison_or_competitor_led_title(normalized_title: str) -> bool:
        comparison_markers = (
            " vs ",
            " versus ",
            " better than ",
            " outperform ",
            " checkmate to ",
            " compared with ",
            " compared to ",
        )
        return any(marker in f" {normalized_title} " for marker in comparison_markers)

    @staticmethod
    def _infer_source_quality(*, title: str, source_name: str) -> str:
        normalized_source = source_name.strip().lower()
        normalized_title = title.strip().lower()
        high_quality_publishers = {
            "reuters",
            "associated press",
            "ap news",
            "bloomberg",
            "the wall street journal",
            "wsj",
            "barron's",
            "financial times",
            "marketwatch",
        }
        opinion_publishers = {
            "the motley fool",
            "seeking alpha",
            "investorplace",
            "zacks",
            "zacks investment research",
        }
        opinion_title_markers = (
            "?",
            "best stock",
            "worth",
            "outperform",
            "buy now",
            "should you buy",
            "can this stock",
        )
        if normalized_source in opinion_publishers:
            return "opinion"
        if any(marker in normalized_title for marker in opinion_title_markers):
            return "opinion"
        if normalized_source in high_quality_publishers:
            return "high"
        return "standard"

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    @staticmethod
    def _infer_sentiment(text: str) -> str:
        lowered = text.lower()
        bullish_tokens = ("partnership", "beats", "growth", "launch", "demand", "expand", "win", "upgrade")
        bearish_tokens = ("risk", "regulation", "export", "delay", "probe", "cuts", "decline", "pressure", "downgrade")
        if any(token in lowered for token in bearish_tokens):
            return "bearish"
        if any(token in lowered for token in bullish_tokens):
            return "bullish"
        return "neutral"

    @staticmethod
    def _infer_topic(text: str) -> str:
        lowered = text.lower()
        if "earnings" in lowered or "results" in lowered:
            return "earnings"
        if "regulation" in lowered or "export" in lowered:
            return "regulation"
        if "partnership" in lowered or "deal" in lowered:
            return "partnership"
        if "product" in lowered or "launch" in lowered:
            return "product"
        return "general"
