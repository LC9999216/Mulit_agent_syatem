import re
from html import unescape

import httpx

from app.config import get_settings


class SecClient:
    BASE_URL = "https://data.sec.gov/submissions"

    def __init__(
        self,
        user_agent: str | None = None,
        use_demo_data: bool | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self.user_agent = user_agent or settings.sec_user_agent
        self.use_demo_data = settings.use_demo_data if use_demo_data is None else use_demo_data
        self.http_client = http_client or httpx.Client(timeout=20.0)

    def fetch_company_documents(self, ticker: str) -> list[dict]:
        if self.use_demo_data:
            return [
                {
                    "doc_type": "10-Q",
                    "doc_date": "2026-04-01",
                    "source_uri": f"demo://filings/{ticker.lower()}-10q",
                    "section": "Business",
                    "content": f"{ticker} disclosed continued demand for accelerated computing platforms.",
                    "sections": [
                        {
                            "section": "Business",
                            "content": f"{ticker} disclosed continued demand for accelerated computing platforms.",
                        },
                        {
                            "section": "MD&A",
                            "content": f"{ticker} reported continued revenue growth driven by accelerated computing platforms.",
                        },
                    ],
                }
            ]

        cik = self._lookup_cik(ticker)
        url = f"{self.BASE_URL}/CIK{cik:010d}.json"
        response = self.http_client.get(url, headers={"User-Agent": self.user_agent})
        response.raise_for_status()
        data = response.json()
        recent = data["filings"]["recent"]
        forms = recent["form"]
        filing_dates = recent["filingDate"]
        accession_numbers = recent["accessionNumber"]
        primary_documents = recent["primaryDocument"]
        documents = []
        for form, filing_date, accession, primary in zip(forms, filing_dates, accession_numbers, primary_documents):
            if form not in {"10-K", "10-Q", "8-K"}:
                continue
            accession_nodashes = accession.replace("-", "")
            source_uri = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodashes}/{primary}"
            try:
                raw_text = self._fetch_document_text(source_uri)
                sections = self._extract_sections(form, raw_text)
                content = sections[0]["content"] if sections else raw_text[:800]
            except httpx.HTTPError:
                sections = []
                content = f"{ticker} filed {form} on {filing_date}."
            documents.append(
                {
                    "doc_type": form,
                    "doc_date": filing_date,
                    "source_uri": source_uri,
                    "section": sections[0]["section"] if sections else "Unknown",
                    "content": content,
                    "sections": sections,
                }
            )
            if len(documents) >= 3:
                break
        return documents

    def _lookup_cik(self, ticker: str) -> int:
        response = self.http_client.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": self.user_agent},
        )
        response.raise_for_status()
        dataset = response.json()
        for item in dataset.values():
            if item["ticker"].upper() == ticker.upper():
                return int(item["cik_str"])
        raise ValueError(f"Unable to find CIK for {ticker}")

    def _fetch_document_text(self, source_uri: str) -> str:
        response = self.http_client.get(source_uri, headers={"User-Agent": self.user_agent})
        response.raise_for_status()
        return self._html_to_text(response.text)

    def _html_to_text(self, html: str) -> str:
        text = re.sub(
            r'(?is)<div[^>]*style="[^"]*display\s*:\s*none[^"]*"[^>]*>.*?</div>',
            " ",
            html,
        )
        text = re.sub(
            r"(?is)<div[^>]*style='[^']*display\s*:\s*none[^']*'[^>]*>.*?</div>",
            " ",
            text,
        )
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</(p|div|h1|h2|h3|h4|li|tr|table|section|article)>", "\n", text)
        text = re.sub(r"(?is)<[^>]+>", " ", text)
        text = unescape(text)
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text)
        return text.strip()

    def _extract_sections(self, doc_type: str, text: str) -> list[dict]:
        if not text:
            return []
        if doc_type in {"10-K", "10-Q"}:
            heading_options = [
                (
                    "Business",
                    [r"\bItem\s+1\.\s+Business\b", r"\bBusiness\b"],
                ),
                (
                    "Risk Factors",
                    [r"\bItem\s+1A\.\s+Risk Factors\b", r"\bRisk Factors\b"],
                ),
                (
                    "MD&A",
                    [
                        r"\bItem\s+(?:2|7)\.\s+Management['’`]s Discussion and Analysis(?: of Financial Condition and Results of Operations)?\b",
                        r"\bManagement['’`]s Discussion and Analysis\b",
                        r"\bMD&A\b",
                    ],
                ),
            ]
        else:
            heading_options = [
                (
                    match.group(0).split(" Results")[0],
                    [re.escape(match.group(0))],
                )
                for match in re.finditer(r"\bItem\s+\d+\.\d+\b", text, flags=re.I)
            ]
            if not heading_options:
                heading_options = [("Current Report", [r"\bCurrent Report\b"])]
        return self._slice_sections(text, heading_options)

    def _slice_sections(self, text: str, heading_options: list[tuple[str, list[str]]]) -> list[dict]:
        all_matches: list[tuple[int, int, str]] = []
        for label, patterns in heading_options:
            best_pattern_matches: list[tuple[int, int, str]] = []
            best_pattern_score: int | None = None
            for pattern in patterns:
                pattern_matches = [
                    (match.start(), match.end(), label)
                    for match in re.finditer(pattern, text, flags=re.I)
                ]
                if pattern_matches:
                    pattern_best_score = max(
                        self._score_section_candidate(text, item, pattern_matches)
                        for item in pattern_matches
                    )
                    if best_pattern_score is None or pattern_best_score > best_pattern_score:
                        best_pattern_score = pattern_best_score
                        best_pattern_matches = pattern_matches
            all_matches.extend(best_pattern_matches)
        all_matches.sort(key=lambda item: item[0])

        if not all_matches:
            fallback = text[:800].strip()
            return [{"section": "Overview", "content": fallback}] if fallback else []

        selected_matches: list[tuple[int, int, str]] = []
        for label, _ in heading_options:
            candidates = [item for item in all_matches if item[2] == label]
            if not candidates:
                continue
            best_match = max(candidates, key=lambda item: self._score_section_candidate(text, item, all_matches))
            if self._score_section_candidate(text, best_match, all_matches) > 0:
                selected_matches.append(best_match)

        selected_matches.sort(key=lambda item: item[0])
        if not selected_matches:
            fallback = text[:800].strip()
            return [{"section": "Overview", "content": fallback}] if fallback else []

        sections: list[dict] = []
        for index, (_, end, label) in enumerate(selected_matches):
            next_start = (
                selected_matches[index + 1][0] if index + 1 < len(selected_matches) else len(text)
            )
            content = self._normalize_section_text(text[end:next_start])
            if not content or self._looks_like_table_of_contents(content):
                continue
            sections.append({"section": label, "content": content[:1200]})
        return sections

    def _score_section_candidate(
        self,
        text: str,
        match: tuple[int, int, str],
        all_matches: list[tuple[int, int, str]],
    ) -> int:
        start, end, _ = match
        next_start = next((candidate[0] for candidate in all_matches if candidate[0] > start), len(text))
        content = self._normalize_section_text(text[end:next_start])
        if not content:
            return -1000
        score = min(len(content), 250)
        if len(content) < 30:
            score -= 120
        if self._looks_like_table_of_contents(content):
            score -= 1200
        if re.search(r"[A-Za-z]{5,}", content):
            score += 50
        if re.search(r"\b(revenue|demand|customer|market|product|risk|results)\b", content, flags=re.I):
            score += 100
        return score

    @staticmethod
    def _normalize_section_text(content: str) -> str:
        return re.sub(r"\s+", " ", content).strip()

    @staticmethod
    def _looks_like_table_of_contents(content: str) -> bool:
        compact = content.strip()
        compact_head = compact[:300]
        if not compact:
            return True
        if re.search(r"\btable of contents\b", compact_head, flags=re.I):
            return True
        if re.search(r"^\d+\s+item\s+\d+[a-z]?\.", compact_head, flags=re.I):
            return True
        if re.search(
            r"^\d+\s+(business|risk factors|management['’`]s discussion and analysis|item\s+\d)",
            compact_head,
            flags=re.I,
        ):
            return True
        if len(re.findall(r"\bitem\s+\d+[a-z]?\.", compact_head[:250], flags=re.I)) >= 2:
            return True
        if re.fullmatch(r"[\d.\sA-Za-z-]{1,30}", compact) and len(compact) < 25:
            return True
        return False
