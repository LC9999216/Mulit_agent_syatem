# Stock Research Multi-Agent System

A multi-agent stock research system built with **FastAPI** and **LangGraph**, featuring auditable evidence chains and structured analysis reports.

## Overview

This system orchestrates multiple specialized AI agents to collaboratively analyze stocks. Each agent focuses on a specific domain (financials, market data, SEC filings, news, etc.), and a supervisor agent coordinates the workflow. The system produces structured, citation-backed research reports with full audit trails.

## Architecture

```
                          +-----------+
                          |  FastAPI  |
                          |   (API)   |
                          +-----+-----+
                                |
                          +-----v-----+
                          |  Analysis |
                          |  Service  |
                          +-----+-----+
                                |
                          +-----v-----+
                          |  Task     |
                          |  Queue    |
                          |(Redis/Mem)|
                          +-----+-----+
                                |
                          +-----v-----+
                          |  Worker   |
                          |  (LangGraph)|
                          +-----+-----+
                                |
              +-----------------+-----------------+
              |                 |                 |
        +-----v-----+   +-----v-----+   +------v------+
        |  Fetch     |   | Supervisor|   |  Data       |
        |  Node      |-->|  Agent    |-->|  Sources    |
        +-----------+   +-----+-----+   +-------------+
                               |
         +---------+-----------+-----------+---------+
         |         |           |           |         |
    +----v---+ +---v----+ +---v----+ +----v---+ +---v----+
    |Filings | |Financial| |Market  | | News   | | Thesis |
    | Agent  | |  Agent  | | Agent  | | Agent  | | Agent  |
    +--------+ +---------+ +--------+ +--------+ +---+----+
                                                      |
                                                +-----v-----+
                                                | Validation|
                                                |   Agent   |
                                                +-----+-----+
                                                      |
                                              +-------+-------+
                                              |               |
                                         Pass |          Fail |
                                              v               v
                                         +--------+    +--------+
                                         |Finalize|    | Repair |
                                         +--------+    +--------+
```

### Agent Pipeline (LangGraph)

The analysis workflow follows a deterministic graph:

1. **Init** - Generate request ID, initialize state
2. **Fetch** - Retrieve SEC filings, news, and market data
3. **Supervisor** - Coordinate and plan the analysis strategy
4. **Filings Agent** - Analyze SEC filings (10-K, 10-Q, 8-K)
5. **Financials Agent** - Analyze financial statements and ratios
6. **Market Agent** - Analyze price action, technicals, and valuation
7. **News Agent** - Analyze recent news and sentiment
8. **Thesis Agent** - Synthesize findings into bull/bear cases
9. **Validation Agent** - Verify claims have proper citations
10. **Repair** (if validation fails) - Strip unsupported statements
11. **Finalize** - Generate the final structured report

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI + Uvicorn |
| Agent Orchestration | LangGraph (StateGraph) |
| Data Validation | Pydantic v2 |
| Configuration | pydantic-settings |
| Task Queue | Redis (with in-memory fallback) |
| Database | PostgreSQL + SQLAlchemy (with SQLite fallback) |
| HTTP Client | httpx |
| Containerization | Docker + Docker Compose |
| Package Manager | uv |
| Testing | pytest |

## Project Structure

```
Mulit-agent syatem/
├── app/
│   ├── agents/              # AI agent implementations
│   │   ├── base.py          # Abstract base agent
│   │   ├── supervisor_agent.py
│   │   ├── filings_agent.py
│   │   ├── financials_agent.py
│   │   ├── market_agent.py
│   │   ├── news_agent.py
│   │   ├── thesis_agent.py
│   │   ├── validation_agent.py
│   │   └── registry.py      # Agent factory
│   ├── data_sources/        # External data adapters
│   │   ├── sec_client.py            # SEC EDGAR
│   │   ├── sec_rss_client.py        # SEC RSS feeds
│   │   ├── market_data_client.py    # Multi-provider market data
│   │   ├── market_data_providers.py # FMP, Polygon, Finnhub
│   │   ├── news_client.py           # News aggregation
│   │   ├── alpaca_news_client.py    # Alpaca News API
│   │   ├── polygon_news_client.py   # Polygon.io News
│   │   └── web_news_search_client.py# Bing News Search
│   ├── graphs/
│   │   └── graph_factory.py # LangGraph workflow definition
│   ├── schemas/             # Pydantic models
│   │   ├── state.py         # Graph state schema
│   │   ├── report.py        # Final report structure
│   │   ├── request.py       # API request schemas
│   │   └── ...              # Domain-specific schemas
│   ├── services/            # Business logic
│   │   ├── analysis_service.py
│   │   ├── report_service.py
│   │   ├── llm_client.py    # LLM integration (OpenAI/DeepSeek)
│   │   ├── runtime.py       # Runtime service container
│   │   └── task_queue.py    # Redis/InMemory queue
│   ├── storage/             # Persistence layer
│   │   ├── db.py            # SQLAlchemy session factory
│   │   ├── models.py        # ORM models
│   │   └── repositories/    # Data access objects
│   ├── workers/
│   │   ├── worker_main.py   # Worker entry point
│   │   └── tasks_analysis.py# Analysis task execution
│   ├── config.py            # Settings (env-based)
│   ├── constants.py         # Enums and constants
│   ├── logging.py           # Logging configuration
│   └── main.py              # FastAPI app factory
├── tests/                   # pytest test suite
├── scripts/                 # Utility scripts
├── reports/                 # Generated report outputs
├── Dockerfile.api           # API container
├── Dockerfile.worker        # Worker container
├── docker-compose.yml       # Full stack orchestration
├── pyproject.toml           # Project metadata & dependencies
└── .env.example             # Environment variable template
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/analyze/company` | Submit a stock analysis request |
| `GET` | `/analysis/{request_id}` | Check analysis status |
| `GET` | `/analysis/{request_id}/runs` | View agent run details |
| `GET` | `/report/{request_id}` | Get structured report (JSON) |
| `GET` | `/report/{request_id}/markdown` | Export report as Markdown |
| `GET` | `/health` | Health check |
| `GET` | `/ready` | Readiness check |

### Example Request

```bash
curl -X POST http://localhost:8000/analyze/company \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'
```

### Example Response

```json
{
  "request_id": "req-a1b2c3d4",
  "status": "pending"
}
```

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- (Optional) Docker & Docker Compose
- (Optional) PostgreSQL and Redis

### Option 1: Local Development (Recommended for quick start)

```powershell
# Clone the repository
git clone https://github.com/LC9999216/Mulit_agent_syatem.git
cd Mulit_agent_syatem

# Create virtual environment and install dependencies
uv venv .venv
uv sync --all-groups

# Copy environment template
cp .env.example .env

# Start the API server (uses demo data by default)
.\.venv\Scripts\uvicorn.exe app.main:create_app --factory --reload
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for the interactive Swagger UI.

### Option 2: Docker Compose (Full Stack)

```bash
# Start all services (API, Worker, PostgreSQL, Redis)
docker compose up --build

# With a market data API key
MARKET_DATA_API_KEY=your_key docker compose up --build
```

### Option 3: Run Worker Separately

The worker processes analysis tasks from the queue:

```powershell
# Start the worker
.\.venv\Scripts\python -m app.workers.worker_main
```

## Configuration

All configuration is managed via environment variables. Copy `.env.example` to `.env` and adjust as needed:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `dev` | Application environment |
| `DATABASE_URL` | `sqlite:///./stock_research.db` | Database connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `USE_DEMO_DATA` | `true` | Use built-in demo data (no API keys needed) |
| `LLM_ENABLED` | `false` | Enable LLM-powered agents |
| `LLM_PROVIDER` | `openai` | LLM provider (`openai` or `deepseek`) |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `MARKET_DATA_API_KEY` | - | Financial Modeling Prep API key |
| `POLYGON_API_KEY` | - | Polygon.io API key |
| `FINNHUB_API_KEY` | - | Finnhub API key |
| `ALPACA_API_KEY` | - | Alpaca Markets API key |
| `SEC_USER_AGENT` | - | SEC EDGAR user agent (required by SEC) |

### LLM Configuration

The system supports optional LLM integration for deeper analysis:

```env
LLM_ENABLED=true
LLM_PROVIDER=openai          # or "deepseek"
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL_SUPERVISOR=gpt-4o-mini
LLM_MODEL_FILINGS=gpt-4o-mini
LLM_MODEL_THESIS=gpt-4o-mini
LLM_MODEL_VALIDATION=gpt-4o-mini
```

## Testing

```powershell
# Run all tests
.\.venv\Scripts\pytest.exe

# Run with verbose output
.\.venv\Scripts\pytest.exe -v

# Run specific test file
.\.venv\Scripts\pytest.exe tests/test_api.py
```

## Report Output

The system generates structured reports with:

- **Executive Summary** - High-level overview
- **Market Analysis** - Price action, valuation, technicals
- **News & Catalysts** - Recent events with citations
- **Bull/Bear Cases** - Supported by evidence chains
- **Trade Plans** - Short-term, mid-term, and long-term strategies
- **Risk Factors** - Uncertainties and thesis breakers
- **Audit Trail** - Full traceability of every claim to its source

Reports can be retrieved as JSON via `/report/{request_id}` or exported as Markdown via `/report/{request_id}/markdown`.

## License

This project is for educational and research purposes.
