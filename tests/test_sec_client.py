import httpx

from app.data_sources.sec_client import SecClient


def test_sec_client_fetches_recent_filing_sections_from_sec_html() -> None:
    submissions_payload = {
        "filings": {
            "recent": {
                "form": ["10-K", "8-K"],
                "filingDate": ["2026-02-25", "2026-03-06"],
                "accessionNumber": ["0001045810-26-000021", "0001045810-26-000024"],
                "primaryDocument": ["nvda-20260125.htm", "nvda-20260302.htm"],
            }
        }
    }
    ten_k_html = """
    <html><body>
    <h1>Business</h1>
    <p>NVIDIA serves hyperscale and enterprise demand for accelerated computing.</p>
    <h1>Management's Discussion and Analysis</h1>
    <p>Revenue increased due to strong data center demand and new AI deployments.</p>
    <h1>Risk Factors</h1>
    <p>Results may fluctuate based on customer concentration and supply constraints.</p>
    </body></html>
    """
    eight_k_html = """
    <html><body>
    <h2>Item 2.02 Results of Operations and Financial Condition</h2>
    <p>The company reported quarterly revenue growth driven by data center products.</p>
    </body></html>
    """
    ticker_payload = {"0": {"ticker": "NVDA", "cik_str": 1045810}}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://www.sec.gov/files/company_tickers.json":
            return httpx.Response(200, json=ticker_payload)
        if url == "https://data.sec.gov/submissions/CIK0001045810.json":
            return httpx.Response(200, json=submissions_payload)
        if url.endswith("/000104581026000021/nvda-20260125.htm"):
            return httpx.Response(200, text=ten_k_html)
        if url.endswith("/000104581026000024/nvda-20260302.htm"):
            return httpx.Response(200, text=eight_k_html)
        raise AssertionError(f"Unexpected SEC url: {url}")

    client = SecClient(
        user_agent="test-agent",
        use_demo_data=False,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    documents = client.fetch_company_documents("NVDA")

    assert len(documents) == 2
    ten_k = next(item for item in documents if item["doc_type"] == "10-K")
    assert ten_k["content"]
    assert ten_k["sections"]
    assert [section["section"] for section in ten_k["sections"]][:3] == ["Business", "MD&A", "Risk Factors"]
    assert "hyperscale" in ten_k["sections"][0]["content"].lower()
    eight_k = next(item for item in documents if item["doc_type"] == "8-K")
    assert eight_k["sections"][0]["section"] == "Item 2.02"
    assert "quarterly revenue growth" in eight_k["sections"][0]["content"].lower()


def test_sec_client_skips_table_of_contents_when_extracting_sections() -> None:
    client = SecClient(user_agent="test-agent", use_demo_data=False)
    text = """
    Table of Contents
    Item 1. Business 4
    Item 1A. Risk Factors 12
    Item 7. Management's Discussion and Analysis 36

    Business
    NVIDIA serves hyperscale and enterprise demand for accelerated computing and AI infrastructure.
    Customers continue deploying accelerated systems across data center workloads.

    Risk Factors
    Revenue may fluctuate due to customer concentration, supply constraints, and geopolitical restrictions.

    Management's Discussion and Analysis
    Revenue increased because of strong data center demand and new AI deployments.
    """

    sections = client._extract_sections("10-K", text)

    assert [section["section"] for section in sections][:3] == ["Business", "Risk Factors", "MD&A"]
    assert "accelerated computing" in sections[0]["content"].lower()
    assert "table of contents" not in sections[0]["content"].lower()
    assert "item 1a. risk factors 12" not in sections[0]["content"].lower()
    assert "customer concentration" in sections[1]["content"].lower()
    assert "revenue increased" in sections[2]["content"].lower()


def test_sec_client_html_to_text_removes_hidden_inline_xbrl_header() -> None:
    client = SecClient(user_agent="test-agent", use_demo_data=False)
    html = """
    <html><body>
    <div style="display:none">
      <ix:header>
        <ix:hidden>
          <ix:nonNumeric>0001045810</ix:nonNumeric>
          <ix:nonNumeric>us-gaap:BusinessAcquisitionAxis</ix:nonNumeric>
        </ix:hidden>
      </ix:header>
    </div>
    <div>Item 7. Management's Discussion and Analysis</div>
    <div>The following discussion and analysis describes revenue growth and data center demand.</div>
    </body></html>
    """

    text = client._html_to_text(html)

    assert "0001045810" not in text
    assert "businessacquisitionaxis" not in text.lower()
    assert "management's discussion and analysis" in text.lower()
    assert "revenue growth and data center demand" in text.lower()
