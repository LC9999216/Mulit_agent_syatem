from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import httpx


class SecRssClient:
    def __init__(
        self,
        *,
        user_agent: str = "stock-research-multiagent contact@example.com",
        feed_url_template: str = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&owner=exclude&count=20&output=atom",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.feed_url_template = feed_url_template
        self.http_client = http_client or httpx.Client(timeout=20.0)

    def fetch_company_news(self, ticker: str, company_aliases: set[str]) -> list[dict]:
        response = self.http_client.get(
            self.feed_url_template.format(ticker=ticker),
            headers={"User-Agent": self.user_agent},
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        events = self._parse_atom_entries(root)
        if not events:
            events = self._parse_rss_items(root)
        normalized_aliases = {alias.upper() for alias in company_aliases if alias}
        normalized_aliases.add(ticker.upper())
        filtered = [event for event in events if self._matches_company(event["title"], normalized_aliases)]
        return filtered[:5]

    def _parse_atom_entries(self, root: ET.Element) -> list[dict]:
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        events: list[dict] = []
        for entry in root.findall("atom:entry", namespace):
            title = (entry.findtext("atom:title", default="", namespaces=namespace) or "").strip()
            link_node = entry.find("atom:link", namespace)
            link = (link_node.attrib.get("href") if link_node is not None else "") or ""
            published = entry.findtext("atom:updated", default="", namespaces=namespace) or ""
            summary = entry.findtext("atom:summary", default="", namespaces=namespace) or title
            if not link:
                continue
            form_type = self._infer_form_type(title, summary)
            events.append(
                {
                    "title": title,
                    "summary": self._build_summary(title=title, summary=summary, form_type=form_type),
                    "source": "SEC RSS",
                    "url": link,
                    "published_at": self._normalize_datetime(published),
                    "sentiment_tag": "neutral",
                    "topic_tag": "filing",
                    "source_class": "regulatory",
                }
            )
        return events

    def _parse_rss_items(self, root: ET.Element) -> list[dict]:
        events: list[dict] = []
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = (item.findtext("description") or "").strip()
            if not link:
                continue
            form_type = self._infer_form_type(title, description)
            events.append(
                {
                    "title": title,
                    "summary": self._build_summary(title=title, summary=description, form_type=form_type),
                    "source": "SEC RSS",
                    "url": link,
                    "published_at": self._normalize_datetime(pub_date),
                    "sentiment_tag": "neutral",
                    "topic_tag": "filing",
                    "source_class": "regulatory",
                }
            )
        return events

    @staticmethod
    def _matches_company(title: str, aliases: set[str]) -> bool:
        upper_title = title.upper()
        return any(alias in upper_title for alias in aliases)

    @staticmethod
    def _infer_form_type(title: str, summary: str) -> str:
        text = f"{title} {summary}".upper()
        for form_type in ("8-K", "10-K", "10-Q", "6-K", "20-F", "DEF 14A", "S-1", "13D", "13G", "4"):
            if form_type in text:
                return form_type
        return "SEC filing"

    @classmethod
    def _build_summary(cls, *, title: str, summary: str, form_type: str) -> str:
        cleaned_title = " ".join(title.split())
        cleaned_summary = " ".join(summary.split())
        if form_type == "8-K":
            return f"The company filed an 8-K, signaling a current report event that may require review of the disclosed update."
        if form_type in {"10-K", "10-Q", "20-F", "6-K"}:
            return f"The company filed {form_type}, adding new regulatory disclosure that should be reviewed for operating, risk, or guidance changes."
        if cleaned_summary:
            return cleaned_summary[:220].rstrip(".") + "."
        return cleaned_title[:220].rstrip(".") + "."

    @staticmethod
    def _normalize_datetime(value: str) -> str | None:
        if not value:
            return None
        try:
            dt = parsedate_to_datetime(value)
        except Exception:
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                return value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat()
