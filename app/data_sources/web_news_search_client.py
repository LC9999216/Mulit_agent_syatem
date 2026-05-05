from __future__ import annotations

from html import unescape
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import httpx

from app.data_sources.polygon_news_client import PolygonNewsClient


class WebNewsSearchClient:
    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=20.0)

    def fetch_company_news(self, ticker: str, company_aliases: set[str] | None = None) -> list[dict]:
        aliases = {ticker.upper()}
        if company_aliases:
            aliases.update(alias.upper() for alias in company_aliases if alias)

        response = self.http_client.get(
            self.base_url,
            params={"q": self._build_query(ticker=ticker, aliases=aliases), "format": "rss"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)

        events: list[dict] = []
        for item in root.findall("./channel/item"):
            link = (item.findtext("link") or "").strip()
            if not link:
                continue
            raw_title = self._clean_html(item.findtext("title") or "")
            rss_title = self._clean_title(raw_title)
            source_name = self._extract_source_name(raw_title, link)
            article = self._fetch_article_details(link)
            title = article["title"] or rss_title
            summary = article["summary"] or self._clean_html(item.findtext("description") or "")
            if not self._is_company_primary(title, aliases):
                continue
            events.append(
                {
                    "title": title,
                    "summary": summary or title,
                    "source": source_name,
                    "url": link,
                    "published_at": self._normalize_pub_date(item.findtext("pubDate") or ""),
                    "sentiment_tag": PolygonNewsClient._infer_sentiment(f"{title} {summary}"),
                    "topic_tag": PolygonNewsClient._infer_topic(f"{title} {summary}"),
                    "source_class": "market_news",
                    "source_quality": PolygonNewsClient._infer_source_quality(title=title, source_name=source_name),
                }
            )
        return [event for event in events if event["url"]][:5]

    @staticmethod
    def _build_query(*, ticker: str, aliases: set[str]) -> str:
        alias_terms = [f'"{alias}"' for alias in sorted(aliases, key=len, reverse=True)[:2]]
        return " ".join([*alias_terms, ticker, "stock", "earnings", "guidance"])

    @staticmethod
    def _clean_html(value: str) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", value or "")
        return " ".join(unescape(cleaned).split())

    @classmethod
    def _clean_title(cls, title: str) -> str:
        cleaned = cls._clean_html(title)
        if " - " in cleaned:
            return cleaned.rsplit(" - ", 1)[0].strip()
        return cleaned

    @classmethod
    def _extract_source_name(cls, title: str, link: str) -> str:
        cleaned = cls._clean_html(title)
        if " - " in cleaned:
            return cleaned.rsplit(" - ", 1)[-1].strip()
        hostname = urlparse(link).hostname or ""
        hostname = hostname.lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname or "Web Search"

    def _fetch_article_details(self, url: str) -> dict[str, str]:
        try:
            response = self.http_client.get(url, follow_redirects=True)
            response.raise_for_status()
        except Exception:
            return {"title": "", "summary": ""}

        html = response.text or ""
        title = self._extract_meta_content(html, "property", "og:title") or self._extract_title_tag(html)
        summary = (
            self._extract_meta_content(html, "property", "og:description")
            or self._extract_meta_content(html, "name", "description")
            or self._extract_article_excerpt(html)
        )
        return {
            "title": self._clean_html(title),
            "summary": self._clean_html(summary),
        }

    @staticmethod
    def _extract_meta_content(html: str, attr_name: str, attr_value: str) -> str:
        pattern = re.compile(
            rf'<meta[^>]+{attr_name}=["\']{re.escape(attr_value)}["\'][^>]+content=["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        match = pattern.search(html)
        if match:
            return match.group(1)
        reverse_pattern = re.compile(
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+{attr_name}=["\']{re.escape(attr_value)}["\']',
            re.IGNORECASE,
        )
        reverse_match = reverse_pattern.search(html)
        return reverse_match.group(1) if reverse_match else ""

    @staticmethod
    def _extract_title_tag(html: str) -> str:
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return match.group(1) if match else ""

    @classmethod
    def _extract_article_excerpt(cls, html: str) -> str:
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
        cleaned = [cls._clean_html(paragraph) for paragraph in paragraphs]
        cleaned = [paragraph for paragraph in cleaned if len(paragraph) > 40]
        if not cleaned:
            return ""
        excerpt = " ".join(cleaned[:2])
        return excerpt[:400].rstrip()

    @staticmethod
    def _normalize_pub_date(value: str) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None

    @classmethod
    def _is_company_primary(cls, title: str, aliases: set[str]) -> bool:
        normalized_title = PolygonNewsClient._normalize_text(title)
        if PolygonNewsClient._is_comparison_or_competitor_led_title(normalized_title):
            return False
        for alias in aliases:
            token = PolygonNewsClient._normalize_text(alias)
            if not token:
                continue
            if normalized_title == token:
                return True
            if normalized_title.startswith(f"{token} "):
                return True
            if f" {token} " in f" {normalized_title} ":
                return True
        return False
