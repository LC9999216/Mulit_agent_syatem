import httpx

from app.data_sources.news_client import NewsClient
from app.data_sources.polygon_news_client import PolygonNewsClient
from app.data_sources.sec_rss_client import SecRssClient
from app.data_sources.web_news_search_client import WebNewsSearchClient


def test_news_client_prefers_direct_company_title_matches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/stock/profile2":
            return httpx.Response(200, json={"name": "NVIDIA Corporation"})
        if request.url.path == "/api/v1/company-news":
            return httpx.Response(
                200,
                json=[
                    {
                        "headline": "IonQ rallies as Nvidia ecosystem expands",
                        "summary": "IonQ moved after commentary mentioning Nvidia.",
                        "source": "Example",
                        "url": "https://example.com/ionq",
                        "datetime": 1713500000,
                    },
                    {
                        "headline": "NVIDIA launches new AI server platform",
                        "summary": "The new platform expands the company's enterprise AI offering.",
                        "source": "Example",
                        "url": "https://example.com/nvda-launch",
                        "datetime": 1713600000,
                    },
                ],
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    client = NewsClient(
        use_demo_data=False,
        fmp_api_key="",
        finnhub_api_key="test-token",
        finnhub_base_url="https://finnhub.io/api/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://finnhub.io/api/v1"),
    )

    events = client.fetch_company_news("NVDA")

    assert len(events) == 1
    assert events[0]["title"] == "NVIDIA launches new AI server platform"


def test_news_client_returns_empty_when_only_indirect_summary_mentions_exist() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/stock/profile2":
            return httpx.Response(200, json={"name": "NVIDIA Corporation"})
        if request.url.path == "/api/v1/company-news":
            return httpx.Response(
                200,
                json=[
                    {
                        "headline": "AI supply chain commentary",
                        "summary": "NVIDIA demand remains strong across hyperscaler and enterprise deployments.",
                        "source": "Example",
                        "url": "https://example.com/nvda-summary",
                        "datetime": 1713600000,
                    }
                ],
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    client = NewsClient(
        use_demo_data=False,
        fmp_api_key="",
        finnhub_api_key="test-token",
        finnhub_base_url="https://finnhub.io/api/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://finnhub.io/api/v1"),
    )

    events = client.fetch_company_news("NVDA")

    assert events == []


def test_news_client_uses_finnhub_direct_title_fallback_when_other_sources_are_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/stock/profile2":
            return httpx.Response(200, json={"name": "NVIDIA Corporation"})
        if request.url.path == "/api/v1/company-news":
            return httpx.Response(
                200,
                json=[
                    {
                        "headline": "NVIDIA launches new Blackwell product updates",
                        "summary": "NVIDIA detailed new product and platform updates for enterprise AI customers.",
                        "source": "Example",
                        "url": "https://example.com/finnhub-nvda",
                        "datetime": 1713600000,
                    }
                ],
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    client = NewsClient(
        use_demo_data=False,
        finnhub_api_key="test-token",
        finnhub_base_url="https://example.com/api/v1",
        sec_rss_client=None,
        alpaca_news_client=None,
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://example.com/api/v1"),
    )

    events = client.fetch_company_news("NVDA")

    assert len(events) == 1
    assert events[0]["url"] == "https://example.com/finnhub-nvda"


def test_news_client_falls_back_when_fmp_news_endpoint_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/stock/profile2":
            return httpx.Response(200, json={"name": "NVIDIA Corporation"})
        if request.url.path == "/stable/news/stock-latest":
            return httpx.Response(402, json={"error": "payment required"})
        if request.url.path == "/api/v1/company-news":
            return httpx.Response(
                200,
                json=[
                    {
                        "headline": "NVIDIA introduces new enterprise AI stack",
                        "summary": "NVIDIA introduced a new enterprise AI stack for customers.",
                        "source": "Example",
                        "url": "https://example.com/fallback-news",
                        "datetime": 1713600000,
                    }
                ],
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    client = NewsClient(
        use_demo_data=False,
        fmp_api_key="fmp-key",
        fmp_base_url="https://financialmodelingprep.com/stable",
        finnhub_api_key="test-token",
        finnhub_base_url="https://example.com/api/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    events = client.fetch_company_news("NVDA")

    assert len(events) == 1
    assert events[0]["url"] == "https://example.com/fallback-news"


def test_sec_rss_client_maps_company_filings_to_news_events() -> None:
    rss_payload = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>NVIDIA CORP 8-K - Current report</title>
          <link>https://www.sec.gov/Archives/edgar/data/1045810/example-8k.htm</link>
          <pubDate>Mon, 20 Apr 2026 12:00:00 GMT</pubDate>
          <description>Form 8-K filed by NVIDIA CORP.</description>
        </item>
      </channel>
    </rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss_payload)

    client = SecRssClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    events = client.fetch_company_news("NVDA", company_aliases={"NVIDIA", "NVIDIA CORP"})

    assert len(events) == 1
    assert events[0]["source"] == "SEC RSS"
    assert events[0]["topic_tag"] == "filing"
    assert events[0]["source_class"] == "regulatory"


def test_polygon_news_client_maps_ticker_news() -> None:
    payload = {
        "results": [
            {
                "title": "NVIDIA launches enterprise AI platform",
                "description": "NVIDIA launched a new enterprise AI platform for data center customers.",
                "article_url": "https://example.com/polygon-nvda",
                "published_utc": "2026-04-20T12:00:00Z",
                "tickers": ["NVDA"],
                "publisher": {"name": "Benzinga"},
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = PolygonNewsClient(
        api_key="polygon-key",
        base_url="https://api.polygon.io",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    events = client.fetch_company_news("NVDA", {"NVIDIA", "NVDA"})

    assert len(events) == 1
    assert events[0]["source"] == "Benzinga"
    assert events[0]["source_class"] == "market_news"
    assert events[0]["source_quality"] == "standard"
    assert events[0]["url"] == "https://example.com/polygon-nvda"


def test_polygon_news_client_rejects_summary_only_mentions() -> None:
    payload = {
        "results": [
            {
                "title": "Nebius lands major AI cloud deals",
                "description": "While Nvidia's investment validates the technology, the article is primarily about Nebius.",
                "article_url": "https://example.com/nebius",
                "published_utc": "2026-04-20T12:00:00Z",
                "tickers": ["NVDA"],
                "publisher": {"name": "Example"},
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = PolygonNewsClient(
        api_key="polygon-key",
        base_url="https://api.polygon.io",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    events = client.fetch_company_news("NVDA", {"NVIDIA", "NVDA"})

    assert events == []


def test_polygon_news_client_rejects_comparison_or_competitor_led_titles() -> None:
    payload = {
        "results": [
            {
                "title": "The Best AI Stock to Buy Now: Micron vs. Nvidia",
                "description": "A comparison article between Micron and Nvidia.",
                "article_url": "https://example.com/micron-vs-nvidia",
                "published_utc": "2026-04-20T12:00:00Z",
                "tickers": ["NVDA"],
                "publisher": {"name": "Example"},
            },
            {
                "title": "Did Amazon Just Say Checkmate to Nvidia?",
                "description": "A competitor-led title discussing Amazon and Nvidia.",
                "article_url": "https://example.com/amazon-checkmate",
                "published_utc": "2026-04-20T11:00:00Z",
                "tickers": ["NVDA"],
                "publisher": {"name": "Example"},
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = PolygonNewsClient(
        api_key="polygon-key",
        base_url="https://api.polygon.io",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    events = client.fetch_company_news("NVDA", {"NVIDIA", "NVDA"})

    assert events == []


def test_polygon_news_client_marks_opinion_publishers_and_question_titles_as_opinion() -> None:
    payload = {
        "results": [
            {
                "title": "Will Nvidia Be Worth $6 Trillion a Year From Now?",
                "description": "A forward-looking opinion piece about Nvidia's upside.",
                "article_url": "https://example.com/fool-opinion",
                "published_utc": "2026-04-20T12:00:00Z",
                "tickers": ["NVDA"],
                "publisher": {"name": "The Motley Fool"},
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = PolygonNewsClient(
        api_key="polygon-key",
        base_url="https://api.polygon.io",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    events = client.fetch_company_news("NVDA", {"NVIDIA", "NVDA"})

    assert len(events) == 1
    assert events[0]["source_quality"] == "opinion"


def test_polygon_news_client_marks_trusted_publishers_as_high_quality() -> None:
    payload = {
        "results": [
            {
                "title": "NVIDIA launches enterprise AI platform",
                "description": "NVIDIA launched a new enterprise AI platform for data center customers.",
                "article_url": "https://example.com/reuters-nvda",
                "published_utc": "2026-04-20T12:00:00Z",
                "tickers": ["NVDA"],
                "publisher": {"name": "Reuters"},
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = PolygonNewsClient(
        api_key="polygon-key",
        base_url="https://api.polygon.io",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    events = client.fetch_company_news("NVDA", {"NVIDIA", "NVDA"})

    assert len(events) == 1
    assert events[0]["source_quality"] == "high"


def test_news_client_aggregates_sec_and_polygon_sources() -> None:
    class StubSecRssClient:
        def fetch_company_news(self, ticker: str, company_aliases: set[str]) -> list[dict]:
            return [
                {
                    "title": "NVIDIA files 8-K on strategic partnership",
                    "summary": "SEC filing indicates NVIDIA disclosed a strategic partnership update.",
                    "source": "SEC RSS",
                    "url": "https://sec.example/nvda-8k",
                    "published_at": "2026-04-20",
                    "sentiment_tag": "neutral",
                    "topic_tag": "filing",
                    "source_class": "regulatory",
                }
            ]

    class StubPolygonNewsClient:
        def fetch_company_news(self, ticker: str, company_aliases: set[str] | None = None) -> list[dict]:
            return [
                {
                    "title": "NVIDIA launches new AI systems",
                    "summary": "NVIDIA launched a new AI system line for enterprise buyers.",
                    "source": "Benzinga",
                    "url": "https://alpaca.example/nvda-ai",
                    "published_at": "2026-04-19",
                    "sentiment_tag": "bullish",
                    "topic_tag": "product",
                    "source_class": "market_news",
                }
            ]

    client = NewsClient(
        use_demo_data=False,
        fmp_api_key="",
        finnhub_api_key="",
        sec_rss_client=StubSecRssClient(),
        polygon_news_client=StubPolygonNewsClient(),
        web_news_search_client=type("StubWebNewsSearchClient", (), {"fetch_company_news": lambda self, ticker, company_aliases=None: []})(),
    )

    events = client.fetch_company_news("NVDA")

    assert len(events) == 2
    assert [event["source_class"] for event in events] == ["regulatory", "market_news"]


def test_web_news_search_client_parses_search_feed_and_article_meta() -> None:
    rss_payload = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>NVIDIA launches new enterprise AI platform - Reuters</title>
          <link>https://example.com/reuters-nvda</link>
          <pubDate>Mon, 20 Apr 2026 12:00:00 GMT</pubDate>
          <description><![CDATA[<p>Reuters coverage of NVIDIA's launch.</p>]]></description>
        </item>
      </channel>
    </rss>"""
    article_html = """
    <html>
      <head>
        <meta property="og:title" content="NVIDIA launches new enterprise AI platform" />
        <meta property="og:description" content="NVIDIA unveiled a new enterprise AI platform aimed at data center customers." />
      </head>
      <body></body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "search.example":
            return httpx.Response(200, text=rss_payload)
        if request.url.host == "example.com":
            return httpx.Response(200, text=article_html)
        raise AssertionError(f"Unexpected url: {request.url}")

    client = WebNewsSearchClient(
        base_url="https://search.example/news/search",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    events = client.fetch_company_news("NVDA", {"NVIDIA", "NVDA"})

    assert len(events) == 1
    assert events[0]["title"] == "NVIDIA launches new enterprise AI platform"
    assert events[0]["source"] == "Reuters"
    assert events[0]["source_quality"] == "high"
    assert "enterprise AI platform" in events[0]["summary"]


def test_news_client_includes_web_search_results_in_aggregation() -> None:
    class StubWebNewsSearchClient:
        def fetch_company_news(self, ticker: str, company_aliases: set[str] | None = None) -> list[dict]:
            return [
                {
                    "title": "NVIDIA wins new AI cloud deployment",
                    "summary": "A new deployment suggests enterprise demand remains active.",
                    "source": "Reuters",
                    "url": "https://example.com/web-news",
                    "published_at": "2026-04-20",
                    "sentiment_tag": "bullish",
                    "topic_tag": "partnership",
                    "source_class": "market_news",
                    "source_quality": "high",
                }
            ]

    client = NewsClient(
        use_demo_data=False,
        fmp_api_key="",
        finnhub_api_key="",
        sec_rss_client=None,
        polygon_news_client=None,
        alpaca_news_client=None,
        web_news_search_client=StubWebNewsSearchClient(),
    )

    events = client.fetch_company_news("NVDA")

    assert len(events) == 1
    assert events[0]["url"] == "https://example.com/web-news"
