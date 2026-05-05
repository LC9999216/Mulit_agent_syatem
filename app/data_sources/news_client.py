from __future__ import annotations

from datetime import date, timedelta
import re

import httpx

from app.data_sources.alpaca_news_client import AlpacaNewsClient
from app.data_sources.polygon_news_client import PolygonNewsClient
from app.data_sources.sec_rss_client import SecRssClient
from app.data_sources.web_news_search_client import WebNewsSearchClient
from app.config import get_settings


class NewsClient:
    def __init__(
        self,
        *,
        use_demo_data: bool | None = None,
        fmp_api_key: str | None = None,
        fmp_base_url: str | None = None,
        finnhub_api_key: str | None = None,
        finnhub_base_url: str | None = None,
        sec_rss_client: SecRssClient | None = None,
        polygon_news_client: PolygonNewsClient | None = None,
        alpaca_news_client: AlpacaNewsClient | None = None,
        web_news_search_client: WebNewsSearchClient | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self.use_demo_data = settings.use_demo_data if use_demo_data is None else use_demo_data
        self.fmp_api_key = settings.market_data_api_key if fmp_api_key is None else fmp_api_key
        self.fmp_base_url = (settings.market_data_base_url if fmp_base_url is None else fmp_base_url).rstrip("/")
        self.finnhub_api_key = settings.finnhub_api_key if finnhub_api_key is None else finnhub_api_key
        self.finnhub_base_url = (settings.finnhub_base_url if finnhub_base_url is None else finnhub_base_url).rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=20.0)
        self.sec_rss_client = sec_rss_client or SecRssClient(
            user_agent=settings.sec_user_agent,
            feed_url_template=settings.sec_rss_feed_url_template,
            http_client=self.http_client,
        )
        self.polygon_news_client = polygon_news_client or PolygonNewsClient(
            api_key=settings.polygon_api_key,
            base_url=settings.polygon_base_url,
            http_client=self.http_client,
        )
        self.alpaca_news_client = alpaca_news_client or AlpacaNewsClient(
            api_key=settings.alpaca_api_key,
            api_secret=settings.alpaca_api_secret,
            base_url=settings.alpaca_news_base_url,
            http_client=self.http_client,
        )
        self.web_news_search_client = web_news_search_client
        if self.web_news_search_client is None and settings.web_news_search_enabled:
            self.web_news_search_client = WebNewsSearchClient(
                base_url=settings.web_news_search_base_url,
                http_client=self.http_client,
            )

    def fetch_company_news(self, ticker: str) -> list[dict]:
        if self.use_demo_data:
            return [
                {
                    "title": f"{ticker} expands AI platform partnerships",
                    "summary": f"Recent coverage suggests {ticker} continues to benefit from AI infrastructure demand and ecosystem expansion.",
                    "source": "demo",
                    "url": f"demo://news/{ticker}/bullish",
                    "published_at": str(date.today()),
                    "sentiment_tag": "bullish",
                    "topic_tag": "partnership",
                },
                {
                    "title": f"{ticker} faces ongoing regulatory scrutiny",
                    "summary": f"Recent coverage highlights export-control and regulatory risk that could affect {ticker}'s product mix and shipments.",
                    "source": "demo",
                    "url": f"demo://news/{ticker}/bearish",
                    "published_at": str(date.today()),
                    "sentiment_tag": "bearish",
                    "topic_tag": "regulation",
                },
            ]

        aliases = self._fetch_company_aliases(ticker)
        aggregated: list[dict] = []

        try:
            aggregated.extend(self.sec_rss_client.fetch_company_news(ticker, aliases))
        except Exception:
            pass

        try:
            aggregated.extend(self.polygon_news_client.fetch_company_news(ticker, aliases))
        except Exception:
            pass

        try:
            if self.web_news_search_client is not None:
                aggregated.extend(self.web_news_search_client.fetch_company_news(ticker, aliases))
        except Exception:
            pass

        try:
            aggregated.extend(self.alpaca_news_client.fetch_company_news(ticker))
        except Exception:
            pass

        if aggregated:
            return self._dedupe_and_sort(aggregated)

        try:
            finnhub_events = self._fetch_finnhub_news(ticker, aliases, allow_summary_fallback=False)
            if finnhub_events:
                return finnhub_events
        except Exception:
            pass

        return []

    def _fetch_finnhub_news(
        self,
        ticker: str,
        aliases: set[str],
        *,
        allow_summary_fallback: bool,
    ) -> list[dict]:
        if not self.finnhub_api_key:
            return []
        end = date.today()
        start = end - timedelta(days=21)
        response = self.http_client.get(
            f"{self.finnhub_base_url}/company-news",
            params={
                "symbol": ticker,
                "from": start.isoformat(),
                "to": end.isoformat(),
                "token": self.finnhub_api_key,
            },
        )
        response.raise_for_status()
        payload = response.json()
        events: list[dict] = []
        for item in (payload or [])[:10]:
            title = item.get("headline") or ""
            summary = item.get("summary") or title
            events.append(
                {
                    "title": title,
                    "summary": summary,
                    "source": item.get("source") or "Finnhub",
                    "url": item.get("url") or "",
                    "published_at": self._timestamp_to_date(item.get("datetime")),
                    "sentiment_tag": self._infer_sentiment(f"{title} {summary}"),
                    "topic_tag": self._infer_topic(f"{title} {summary}"),
                }
            )
        return self._normalize_events(events, ticker, aliases, allow_summary_fallback=allow_summary_fallback)

    def _fetch_fmp_news(self, ticker: str, aliases: set[str]) -> list[dict]:
        if not self.fmp_api_key:
            return []
        response = self.http_client.get(
            f"{self.fmp_base_url}/news/stock-latest",
            params={"page": 0, "limit": 25, "apikey": self.fmp_api_key},
        )
        response.raise_for_status()
        payload = response.json()
        events: list[dict] = []
        for item in payload or []:
            symbols = item.get("symbol") or item.get("symbols") or []
            if isinstance(symbols, str):
                matched = ticker in symbols.upper()
            else:
                matched = ticker in [str(symbol).upper() for symbol in symbols]
            if not matched:
                continue
            title = item.get("title") or ""
            summary = item.get("text") or item.get("snippet") or title
            events.append(
                {
                    "title": title,
                    "summary": summary,
                    "source": item.get("site") or item.get("publisher") or "FMP",
                    "url": item.get("url") or "",
                    "published_at": item.get("publishedDate"),
                    "sentiment_tag": self._infer_sentiment(f"{title} {summary}"),
                    "topic_tag": self._infer_topic(f"{title} {summary}"),
                }
            )
            if len(events) >= 10:
                break
        return self._normalize_events(events, ticker, aliases, allow_summary_fallback=False)

    def _fetch_company_aliases(self, ticker: str) -> set[str]:
        aliases = {ticker.upper()}
        if self.finnhub_api_key:
            try:
                response = self.http_client.get(
                    f"{self.finnhub_base_url}/stock/profile2",
                    params={"symbol": ticker, "token": self.finnhub_api_key},
                )
                response.raise_for_status()
                profile = response.json() or {}
                aliases.update(self._aliases_from_name(profile.get("name")))
            except Exception:
                pass
        if self.fmp_api_key:
            try:
                response = self.http_client.get(
                    f"{self.fmp_base_url}/profile",
                    params={"symbol": ticker, "apikey": self.fmp_api_key},
                )
                response.raise_for_status()
                payload = response.json() or []
                profile = payload[0] if isinstance(payload, list) and payload else payload
                aliases.update(self._aliases_from_name((profile or {}).get("companyName")))
            except Exception:
                pass
        return {alias for alias in aliases if alias}

    def _normalize_events(
        self,
        events: list[dict],
        ticker: str,
        aliases: set[str],
        *,
        allow_summary_fallback: bool,
    ) -> list[dict]:
        direct_matches: list[dict] = []
        fallback_matches: list[dict] = []
        seen_urls: set[str] = set()

        for event in events:
            url = event.get("url") or ""
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = event.get("title") or ""
            summary = event.get("summary") or ""
            if self._is_direct_company_news(title, ticker, aliases):
                direct_matches.append(event)
                continue
            if allow_summary_fallback and self._mentions_company(summary, ticker, aliases):
                fallback_matches.append(event)

        selected = direct_matches or fallback_matches
        return self._dedupe_and_sort(selected)

    @classmethod
    def _is_direct_company_news(cls, title: str, ticker: str, aliases: set[str]) -> bool:
        if not title:
            return False
        normalized_title = cls._normalize_text(title)
        tokens = {cls._normalize_text(ticker)}
        tokens.update(cls._normalize_text(alias) for alias in aliases if alias)
        for token in tokens:
            if not token:
                continue
            if normalized_title == token:
                return True
            if normalized_title.startswith(f"{token} "):
                return True
            if normalized_title.startswith(f"{token}s "):
                return True
        return False

    @classmethod
    def _mentions_company(cls, text: str, ticker: str, aliases: set[str]) -> bool:
        if not text:
            return False
        normalized = cls._normalize_text(text)
        tokens = {cls._normalize_text(ticker)}
        tokens.update(cls._normalize_text(alias) for alias in aliases if alias)
        return any(token and token in normalized for token in tokens)

    @staticmethod
    def _aliases_from_name(name: str | None) -> set[str]:
        if not name:
            return set()
        aliases = {name}
        normalized = re.sub(r"\b(corporation|corp|incorporated|inc|ltd|limited|holdings|group|company|co)\b", "", name, flags=re.IGNORECASE)
        normalized = " ".join(normalized.split())
        if normalized:
            aliases.add(normalized)
        words = [part for part in re.split(r"[\s,/()-]+", normalized) if part]
        if words:
            aliases.add(" ".join(words[:2]))
            aliases.add(words[0])
        return {alias for alias in aliases if alias}

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    @staticmethod
    def _dedupe_and_sort(events: list[dict]) -> list[dict]:
        deduped: list[dict] = []
        seen_urls: set[str] = set()
        for event in events:
            url = event.get("url") or ""
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            deduped.append(event)
        deduped.sort(key=lambda item: item.get("published_at") or "", reverse=True)
        deduped.sort(key=lambda item: 0 if item.get("source_class") == "regulatory" else 1)
        return deduped[:8]

    @staticmethod
    def _timestamp_to_date(value) -> str | None:
        if value is None:
            return None
        try:
            return date.fromtimestamp(int(value)).isoformat()
        except Exception:
            return None

    @staticmethod
    def _infer_sentiment(text: str) -> str:
        lowered = text.lower()
        bullish_tokens = ("partnership", "beats", "growth", "launch", "demand", "expands", "wins")
        bearish_tokens = ("risk", "regulation", "export", "delay", "probe", "cuts", "decline", "pressure")
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
