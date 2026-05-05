from __future__ import annotations

from datetime import date, timedelta

import httpx


class AlpacaNewsClient:
    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        base_url: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=20.0)

    def fetch_company_news(self, ticker: str) -> list[dict]:
        if not self.api_key or not self.api_secret:
            return []

        end = date.today()
        start = end - timedelta(days=14)
        response = self.http_client.get(
            self.base_url,
            params={
                "symbols": ticker,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "sort": "desc",
                "limit": 10,
                "include_content": False,
            },
            headers={
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.api_secret,
            },
        )
        response.raise_for_status()
        payload = response.json() or {}
        events: list[dict] = []
        for item in payload.get("news", []) or []:
            symbols = [str(symbol).upper() for symbol in item.get("symbols") or []]
            if ticker.upper() not in symbols:
                continue
            title = item.get("headline") or ""
            summary = item.get("summary") or title
            events.append(
                {
                    "title": title,
                    "summary": summary,
                    "source": item.get("source") or "Alpaca News",
                    "url": item.get("url") or "",
                    "published_at": item.get("created_at"),
                    "sentiment_tag": self._infer_sentiment(f"{title} {summary}"),
                    "topic_tag": self._infer_topic(f"{title} {summary}"),
                    "source_class": "market_news",
                }
            )
        return [event for event in events if event["url"]][:6]

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
